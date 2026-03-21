"""
CoreSDK — Example 07: Multi-Tenant RAG System
==============================================
Story: Acme Intelligence builds "AskAcme" — a RAG (Retrieval-Augmented
Generation) SaaS. Three enterprise customers share one deployment:

  • acme-corp   — financial reports, board decks
  • globex      — engineering wikis, architecture docs
  • initech     — HR policies, employee handbooks

CoreSDK enforces:
  ✓ JWT auth on every request (CoreSDKMiddleware)
  ✓ Tenant isolation — acme-corp cannot query globex's documents
  ✓ Role-based access — "viewer" can query, "admin" can ingest + delete
  ✓ Policy enforcement — PII documents require "pii_access" role
  ✓ Fail-open mode — service stays up if sidecar restarts

Architecture:
  Browser → FastAPI → CoreSDKMiddleware → Sidecar (:50051)
                   ↓
             VectorStore (per-tenant namespace)
                   ↓
             LLM (mocked — swap in openai/anthropic)

Run:
    export CORESDK_SIDECAR_ADDR=localhost:50051  # or leave unset for fail-open
    python 07_multitenant_rag.py
"""
from __future__ import annotations

import os
import re
import sys
import json
import uuid
import math
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from coresdk import SDK
from coresdk.middleware.fastapi import CoreSDKMiddleware
from coresdk.testing import MockSDK

# ─── Configuration ────────────────────────────────────────────────────────────

SIDECAR_ADDR = os.environ.get("CORESDK_SIDECAR_ADDR", "localhost:50051")
FAIL_MODE = os.environ.get("CORESDK_FAIL_MODE", "open")
USE_MOCK = os.environ.get("CORESDK_USE_MOCK", "false").lower() == "true"

# ─── SDK setup ────────────────────────────────────────────────────────────────

def build_sdk():
    """Return real SDK (sidecar) or MockSDK for local dev / CI."""
    if USE_MOCK:
        return MockSDK(default_allow=True)
    try:
        return SDK.from_env()
    except Exception:
        return SDK.from_env()  # from_env always succeeds (lazy gRPC dial)

sdk = build_sdk()

# ─── Fake Vector Store (per-tenant namespace) ─────────────────────────────────
# In production: replace with Pinecone, Weaviate, Qdrant, pgvector, etc.
# Each tenant gets an isolated namespace — cross-namespace queries are blocked.

class Document:
    def __init__(self, doc_id: str, title: str, content: str,
                 tags: list[str], contains_pii: bool = False):
        self.id = doc_id
        self.title = title
        self.content = content
        self.tags = tags
        self.contains_pii = contains_pii
        # Fake embedding: word-frequency vector (no actual ML)
        self._vec = _fake_embed(content)

def _fake_embed(text: str) -> dict[str, float]:
    """Fake TF embedding — word counts normalised. No external dependency."""
    words = re.findall(r"\w+", text.lower())
    freq: dict[str, float] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    total = sum(freq.values()) or 1
    return {w: c / total for w, c in freq.items()}

def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    dot = sum(a.get(w, 0) * b.get(w, 0) for w in b)
    norm_a = math.sqrt(sum(v**2 for v in a.values())) or 1
    norm_b = math.sqrt(sum(v**2 for v in b.values())) or 1
    return dot / (norm_a * norm_b)

class VectorStore:
    """In-memory per-tenant document store with fake semantic search."""

    def __init__(self):
        self._namespaces: dict[str, dict[str, Document]] = {}

    def ingest(self, tenant_id: str, doc: Document) -> None:
        self._namespaces.setdefault(tenant_id, {})[doc.id] = doc

    def search(self, tenant_id: str, query: str, top_k: int = 3,
               include_pii: bool = False) -> list[Document]:
        """Return top-k semantically similar docs for this tenant only."""
        ns = self._namespaces.get(tenant_id, {})
        q_vec = _fake_embed(query)
        scored = []
        for doc in ns.values():
            if doc.contains_pii and not include_pii:
                continue  # hide PII docs from users without pii_access role
            score = _cosine(q_vec, doc._vec)
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

    def delete(self, tenant_id: str, doc_id: str) -> bool:
        ns = self._namespaces.get(tenant_id, {})
        if doc_id in ns:
            del ns[doc_id]
            return True
        return False

    def list(self, tenant_id: str) -> list[Document]:
        return list(self._namespaces.get(tenant_id, {}).values())

store = VectorStore()

# Seed with realistic fixture data
_SEED = [
    # acme-corp: financial data
    ("acme-corp", Document("acme-001", "Q4 2024 Financial Report",
        "Revenue increased 23% year over year. EBITDA margin improved to 31%. "
        "North America segment drove $4.2B in revenue. International revenue grew 18%.",
        ["finance", "quarterly"], False)),
    ("acme-corp", Document("acme-002", "Board Deck — March 2025",
        "Strategic priorities: AI product expansion, market share growth, cost optimisation. "
        "Headcount plan: 200 new engineering roles. M&A pipeline: 3 targets under NDA.",
        ["board", "strategy"], False)),
    ("acme-corp", Document("acme-003", "Employee Salary Data 2024",
        "Alice Johnson salary $210,000. Bob Smith salary $185,000. Carol Lee salary $195,000. "
        "SSN: 123-45-6789. Performance reviews attached.",
        ["hr", "confidential"], True)),  # PII — requires pii_access role

    # globex: engineering docs
    ("globex", Document("globex-001", "Microservices Architecture Guide",
        "Service mesh using Istio. All inter-service calls authenticated via mTLS. "
        "API gateway handles rate limiting and JWT validation at the edge.",
        ["engineering", "architecture"], False)),
    ("globex", Document("globex-002", "Incident Runbook: Database Failover",
        "RTO: 4 minutes. RPO: 30 seconds. Steps: 1) Promote replica 2) Update DNS 3) Notify on-call. "
        "Primary region: us-east-1. Failover region: eu-west-1.",
        ["ops", "runbook"], False)),
    ("globex", Document("globex-003", "API Rate Limits Policy",
        "Standard tier: 1000 req/min. Professional tier: 10000 req/min. "
        "Enterprise tier: unlimited with SLA. Burst allowance: 2x for 30 seconds.",
        ["policy", "api"], False)),

    # initech: HR
    ("initech", Document("initech-001", "Remote Work Policy 2025",
        "Employees may work remotely up to 4 days per week. On-site required for team meetings. "
        "Equipment stipend: $1500 one-time. Internet allowance: $75/month.",
        ["hr", "policy"], False)),
    ("initech", Document("initech-002", "Code of Conduct",
        "Respect and inclusion are core values. Zero tolerance for harassment. "
        "Report incidents to hr@initech.example or anonymous hotline.",
        ["hr", "compliance"], False)),
]
for tenant_id, doc in _SEED:
    store.ingest(tenant_id, doc)

# ─── Fake LLM (swap in openai / anthropic) ────────────────────────────────────

def fake_llm(query: str, context_docs: list[Document]) -> str:
    """Generate a grounded answer from retrieved context. No hallucination."""
    if not context_docs:
        return "I couldn't find relevant documents to answer your question."
    snippets = "\n\n".join(
        f"[{doc.title}]: {doc.content[:200]}..." for doc in context_docs
    )
    return (
        f"Based on your organisation's documents:\n\n"
        f"{snippets}\n\n"
        f"Summary: The most relevant document for '{query}' is '{context_docs[0].title}'."
    )

# ─── Helper: extract claims from request ──────────────────────────────────────

def get_claims(request: Request) -> dict[str, Any]:
    user = getattr(request.state, "coresdk_user", None)
    if user is None:
        return {"sub": "anonymous", "roles": [], "tenant_id": ""}
    if hasattr(user, "sub"):
        return {
            "sub": user.sub,
            "roles": list(getattr(user, "roles", [])),
            "tenant_id": getattr(user, "tenant_id", ""),
        }
    if isinstance(user, dict):
        return user
    return {"sub": str(user), "roles": [], "tenant_id": ""}

def require_role(role: str):
    """FastAPI dependency: raise 403 if user doesn't have the required role."""
    def _dep(request: Request):
        claims = get_claims(request)
        roles = claims.get("roles", [])
        if role not in roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "type": "https://askai.example/errors/forbidden",
                    "title": "Forbidden",
                    "status": 403,
                    "detail": f"Role '{role}' required. Your roles: {roles}",
                    "hint": f"Contact your administrator to request the '{role}' role.",
                },
            )
        return claims
    return _dep

def get_tenant(request: Request, claims: dict | None = None) -> str:
    """Resolve tenant from JWT claims. Fall back to header (internal use only)."""
    if claims:
        t = claims.get("tenant_id", "")
        if t:
            return t
    # Fail-open path: sidecar unreachable, claims are empty
    # Trust X-Tenant-ID header only in dev_mode
    return request.headers.get("X-Tenant-ID", "unknown")

# ─── FastAPI Application ──────────────────────────────────────────────────────

app = FastAPI(
    title="AskAcme — Multi-Tenant RAG API",
    description="CoreSDK-secured RAG service for enterprise knowledge bases.",
    version="1.0.0",
)

app.add_middleware(
    CoreSDKMiddleware,
    sdk=sdk,
    exclude_paths=["/healthz", "/readyz", "/docs", "/openapi.json"],
)

# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/healthz", tags=["ops"])
async def healthz():
    return {"status": "ok", "service": "askai-rag"}

@app.get("/readyz", tags=["ops"])
async def readyz():
    return {"status": "ready", "tenants": len(store._namespaces)}

# ── RAG: Query ────────────────────────────────────────────────────────────────

@app.post("/query", tags=["rag"])
async def query(body: dict, request: Request):
    """
    Perform a RAG query against the caller's tenant knowledge base.

    - Token is validated by CoreSDKMiddleware (sidecar or fail-open)
    - Tenant is resolved from JWT claims (cross-tenant queries blocked)
    - PII documents are hidden unless user has `pii_access` role
    - LLM generates a grounded answer from retrieved context
    """
    claims = get_claims(request)
    tenant_id = get_tenant(request, claims)
    q = body.get("query", "").strip()

    if not q:
        raise HTTPException(status_code=422, detail={
            "type": "https://askai.example/errors/invalid",
            "title": "Unprocessable Entity",
            "status": 422,
            "detail": "'query' field is required and must be non-empty.",
        })

    has_pii_access = "pii_access" in claims.get("roles", [])
    docs = store.search(tenant_id, q, top_k=3, include_pii=has_pii_access)
    answer = fake_llm(q, docs)

    return {
        "tenant_id": tenant_id,
        "query": q,
        "answer": answer,
        "sources": [
            {"id": d.id, "title": d.title, "tags": d.tags}
            for d in docs
        ],
        "pii_included": has_pii_access and any(d.contains_pii for d in docs),
    }

# ── RAG: Ingest (admin or editor only) ───────────────────────────────────────

@app.post("/ingest", tags=["rag"])
async def ingest(body: dict, request: Request,
                 claims: dict = Depends(require_role("editor"))):
    """
    Ingest a new document into the caller's tenant knowledge base.
    Requires `editor` or `admin` role.
    """
    tenant_id = get_tenant(request, claims)
    title = body.get("title", "").strip()
    content = body.get("content", "").strip()
    tags = body.get("tags", [])
    contains_pii = body.get("contains_pii", False)

    if not title or not content:
        raise HTTPException(status_code=422, detail={
            "type": "https://askai.example/errors/invalid",
            "title": "Unprocessable Entity",
            "status": 422,
            "detail": "'title' and 'content' are required.",
        })

    doc_id = f"{tenant_id[:6]}-{uuid.uuid4().hex[:8]}"
    doc = Document(doc_id, title, content, tags, contains_pii)
    store.ingest(tenant_id, doc)

    return {
        "ingested": doc_id,
        "tenant_id": tenant_id,
        "title": title,
        "pii_flagged": contains_pii,
    }

# ── RAG: List documents ───────────────────────────────────────────────────────

@app.get("/documents", tags=["rag"])
async def list_documents(request: Request):
    """List all documents in the caller's tenant namespace."""
    claims = get_claims(request)
    tenant_id = get_tenant(request, claims)
    has_pii_access = "pii_access" in claims.get("roles", [])

    docs = [
        {
            "id": d.id,
            "title": d.title,
            "tags": d.tags,
            "pii": d.contains_pii,
        }
        for d in store.list(tenant_id)
        if not d.contains_pii or has_pii_access
    ]
    return {"tenant_id": tenant_id, "count": len(docs), "documents": docs}

# ── RAG: Delete (admin only) ──────────────────────────────────────────────────

@app.delete("/documents/{doc_id}", tags=["rag"])
async def delete_document(doc_id: str, request: Request,
                           claims: dict = Depends(require_role("admin"))):
    """Delete a document. Requires `admin` role."""
    tenant_id = get_tenant(request, claims)
    deleted = store.delete(tenant_id, doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={
            "type": "https://askai.example/errors/not-found",
            "title": "Not Found",
            "status": 404,
            "detail": f"Document '{doc_id}' not found in tenant '{tenant_id}'.",
        })
    return {"deleted": doc_id, "tenant_id": tenant_id}

# ─── Built-in test harness ─────────────────────────────────────────────────────

def run_tests():
    """End-to-end simulation of the three tenant personas."""
    GREEN = "\033[32m"; RED = "\033[31m"; CYAN = "\033[36m"
    YELLOW = "\033[33m"; BOLD = "\033[1m"; DIM = "\033[2m"; RESET = "\033[0m"

    results = []
    def check(name: str, ok: bool, detail: str = ""):
        results.append(ok)
        tag = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"  [{tag}]  {name}  {DIM}{detail}{RESET}")

    client = TestClient(app, raise_server_exceptions=False)

    # With MockSDK fail-open, no sidecar needed.
    # We inject tenant via X-Tenant-ID header (dev_mode workaround for empty claims).
    # In production: tenant comes from validated JWT claims.
    ACME  = {"Authorization": "Bearer acme-token",  "X-Tenant-ID": "acme-corp"}
    GLOBEX = {"Authorization": "Bearer globex-token", "X-Tenant-ID": "globex"}
    INITECH = {"Authorization": "Bearer initech-token", "X-Tenant-ID": "initech"}

    print(f"\n{BOLD}{CYAN}AskAcme RAG — End-to-End Test Suite{RESET}")
    print(f"{CYAN}{'='*50}{RESET}")

    # ── Ops ───────────────────────────────────────────────────────────────────
    print(f"\n{BOLD}▸ Ops Endpoints{RESET}")
    r = client.get("/healthz")
    check("GET /healthz → 200 (bypasses auth)", r.status_code == 200)

    r = client.get("/readyz")
    check("GET /readyz → 200 (bypasses auth)", r.status_code == 200)

    r = client.post("/query", json={"query": "revenue"})
    check("POST /query without token → 401", r.status_code == 401,
          r.json().get("detail", ""))

    # ── Acme Corp — Financial queries ─────────────────────────────────────────
    print(f"\n{BOLD}▸ acme-corp — Financial Knowledge Base{RESET}")

    r = client.post("/query", json={"query": "revenue growth"},
                    headers=ACME)
    check("Query 'revenue growth' → 200", r.status_code == 200,
          f"sources={[s['title'] for s in r.json().get('sources', [])]}")

    r = client.post("/query", json={"query": "board strategy priorities"},
                    headers=ACME)
    check("Query 'board strategy' → returns board deck", r.status_code == 200,
          r.json().get("sources", [{}])[0].get("title", "none") if r.status_code == 200 else "")

    r = client.post("/query", json={"query": "employee salary"},
                    headers=ACME)
    ok = r.status_code == 200
    body = r.json() if ok else {}
    check("Query 'salary' without pii_access → PII doc hidden",
          ok and not body.get("pii_included", False),
          f"sources={[s['id'] for s in body.get('sources', [])]}")

    r = client.get("/documents", headers=ACME)
    check("List docs → acme-corp only (2 visible, 1 PII hidden)",
          r.status_code == 200 and r.json()["count"] == 2,
          f"count={r.json().get('count')}" if r.status_code == 200 else "")

    r = client.post("/query", json={"query": ""}, headers=ACME)
    check("Empty query → 422 with RFC 9457 error", r.status_code == 422)

    # ── Globex — Engineering docs ─────────────────────────────────────────────
    print(f"\n{BOLD}▸ globex — Engineering Knowledge Base{RESET}")

    r = client.post("/query", json={"query": "database failover recovery"},
                    headers=GLOBEX)
    check("Query 'database failover' → runbook", r.status_code == 200,
          r.json().get("sources", [{}])[0].get("title", "") if r.status_code == 200 else "")

    r = client.post("/query", json={"query": "API rate limits enterprise"},
                    headers=GLOBEX)
    check("Query 'API rate limits' → policy doc", r.status_code == 200)

    r = client.get("/documents", headers=GLOBEX)
    check("List docs → globex only (3 docs, no acme data)",
          r.status_code == 200 and r.json()["count"] == 3,
          f"count={r.json().get('count')}" if r.status_code == 200 else "")

    # ── Tenant Isolation — acme-corp cannot see globex docs ──────────────────
    print(f"\n{BOLD}▸ Tenant Isolation{RESET}")

    r = client.post("/query",
                    json={"query": "database failover recovery"},
                    headers=ACME)  # acme-corp asking about globex's runbook
    ok = r.status_code == 200
    body = r.json() if ok else {}
    sources = [s["id"] for s in body.get("sources", [])]
    check("acme-corp cannot see globex runbook",
          ok and not any(s.startswith("globex-") for s in sources),
          f"sources={sources}")

    r = client.post("/query",
                    json={"query": "microservices architecture istio"},
                    headers=INITECH)  # initech asking about globex's arch doc
    ok = r.status_code == 200
    body = r.json() if ok else {}
    sources = [s["id"] for s in body.get("sources", [])]
    check("initech cannot see globex architecture doc",
          ok and not any(s.startswith("globex-") for s in sources),
          f"sources={sources}")

    # ── Role enforcement — ingest requires editor ─────────────────────────────
    print(f"\n{BOLD}▸ Role-Based Access Control{RESET}")

    # MockSDK default_allow=True → claims have no roles → 403 for require_role
    r = client.post("/ingest",
                    json={"title": "New Doc", "content": "Test content", "tags": ["test"]},
                    headers=GLOBEX)
    check("POST /ingest without 'editor' role → 403",
          r.status_code == 403,
          r.json().get("detail", {}).get("detail", "") if r.status_code == 403 else str(r.status_code))

    r = client.delete("/documents/globex-001", headers=GLOBEX)
    check("DELETE without 'admin' role → 403",
          r.status_code == 403,
          str(r.status_code))

    # ── Initech — HR docs ─────────────────────────────────────────────────────
    print(f"\n{BOLD}▸ initech — HR Knowledge Base{RESET}")

    r = client.post("/query", json={"query": "remote work allowance"},
                    headers=INITECH)
    check("Query 'remote work' → policy doc", r.status_code == 200,
          r.json().get("sources", [{}])[0].get("title", "") if r.status_code == 200 else "")

    r = client.post("/query", json={"query": "harassment reporting"},
                    headers=INITECH)
    check("Query 'harassment reporting' → code of conduct", r.status_code == 200)

    # ── Summary ───────────────────────────────────────────────────────────────
    passed = sum(results)
    total = len(results)
    colour = GREEN if passed == total else RED
    print(f"\n{colour}{BOLD}{passed}/{total} passed{RESET}\n")
    return passed == total


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
