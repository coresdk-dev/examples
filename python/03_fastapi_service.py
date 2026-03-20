"""
CoreSDK — Example 03: FastAPI Service with Auth + Policy
=========================================================
A realistic FastAPI document service:
  - All routes protected by JWT (CoreSDKMiddleware)
  - Fine-grained per-route policy (require_auth dependency)
  - Tenant-scoped data access
  - RFC 9457 structured errors
  - PII-safe tracing with @trace

Run:
    pip install coresdk fastapi httpx uvicorn
    python 03_fastapi_service.py          # runs built-in test client
    uvicorn 03_fastapi_service:app --reload  # or run as a real server
"""
import sys
sys.path.insert(0, "/tmp/coresdk-sdk-python")

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from coresdk._types import AuthDecision
from coresdk.middleware.fastapi import CoreSDKMiddleware, require_auth
from coresdk.errors._rfc9457 import ProblemDetailError
from coresdk.testing._mock import MockSDK
from coresdk.tracing.decorator import trace

# ── SDK setup ─────────────────────────────────────────────────────────────────
# Production: replace MockSDK with CoreSDKClient(SDKConfig.from_env())
sdk = MockSDK(
    default_claims={"sub": "alice", "tenant_id": "acme-corp", "roles": ["admin", "user"]},
)
# Ensure middleware enforces auth (dev_mode=False = no bypass on missing token)
sdk.config = type("C", (), {
    "dev_mode": False, "fail_mode": "open", "tenant_id": "acme-corp", "service_name": "doc-service"
})()

# Make carol a viewer-only user
sdk.set_token_decision("carol-token", AuthDecision(
    allowed=True,
    claims={"sub": "carol", "tenant_id": "acme-corp", "roles": ["viewer"]},
))
# Revoke a compromised token
sdk.set_token_rejected("revoked-token", reason="token has been revoked")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="Document Service", version="1.0.0")

# All routes require a valid JWT — no token = 401 immediately
app.add_middleware(CoreSDKMiddleware, sdk=sdk, exclude_paths=["/healthz", "/docs", "/openapi.json"])

# ── In-memory document store (per tenant) ─────────────────────────────────────
_docs: dict[str, dict] = {
    "acme-corp": {
        "doc-1": {"title": "Q4 Report",       "content": "Revenue up 23%", "owner": "alice"},
        "doc-2": {"title": "Roadmap 2025",    "content": "Phase 1: CoreSDK", "owner": "alice"},
        "doc-3": {"title": "Employee List",   "content": "Alice, Bob, Carol", "owner": "alice"},
    }
}

def get_current_user(request: Request) -> dict:
    """Extract user context injected by CoreSDKMiddleware."""
    user = getattr(request.state, "coresdk_user", None)
    if user is None:
        # fail-open: middleware let the request through without claims
        return AuthDecision(allowed=True, claims={"sub": "anonymous", "roles": []})
    return user.claims if hasattr(user, "claims") else user

def require_role(role: str):
    """Dependency: raise 403 if user doesn't have the required role."""
    def _check(request: Request):
        user = get_current_user(request)
        claims = user if isinstance(user, dict) else {}
        roles = claims.get("roles", [])
        if role not in roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "type":   "https://coresdk.io/errors/forbidden",
                    "title":  "Forbidden",
                    "status": 403,
                    "detail": f"Required role '{role}' not present. Your roles: {roles}",
                },
            )
        return claims
    return _check

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/documents")
@trace(intent="list-documents")
async def list_documents(request: Request):
    """List documents for the caller's tenant. Any authenticated user can read."""
    user   = get_current_user(request)
    claims = user if isinstance(user, dict) else {}
    tenant = claims.get("tenant_id", "unknown")
    docs   = _docs.get(tenant, {})
    return {
        "tenant":    tenant,
        "user":      claims.get("sub"),
        "documents": [{"id": k, "title": v["title"]} for k, v in docs.items()],
    }

@app.get("/documents/{doc_id}")
@trace(intent="get-document")
async def get_document(doc_id: str, request: Request):
    """Get a specific document. Viewer+ can read."""
    user   = get_current_user(request)
    claims = user if isinstance(user, dict) else {}
    tenant = claims.get("tenant_id", "unknown")
    doc    = _docs.get(tenant, {}).get(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail={
            "type":   "https://coresdk.io/errors/not-found",
            "title":  "Not Found",
            "status": 404,
            "detail": f"Document '{doc_id}' not found in tenant '{tenant}'",
        })
    return {"id": doc_id, "tenant": tenant, **doc}

@app.post("/documents")
@trace(intent="create-document")
async def create_document(body: dict, claims=Depends(require_role("user"))):
    """Create a document. Requires 'user' role."""
    tenant = claims.get("tenant_id", "default")
    doc_id = f"doc-{len(_docs.get(tenant, {})) + 10}"
    _docs.setdefault(tenant, {})[doc_id] = {
        "title":   body.get("title", "Untitled"),
        "content": body.get("content", ""),
        "owner":   claims.get("sub"),
    }
    return {"created": doc_id, "tenant": tenant}

@app.delete("/documents/{doc_id}")
@trace(intent="delete-document")
async def delete_document(doc_id: str, claims=Depends(require_role("admin"))):
    """Delete a document. Requires 'admin' role."""
    tenant = claims.get("tenant_id", "default")
    if doc_id not in _docs.get(tenant, {}):
        raise HTTPException(status_code=404, detail={
            "type":   "https://coresdk.io/errors/not-found",
            "title":  "Not Found",
            "status": 404,
            "detail": f"Document '{doc_id}' not found",
        })
    del _docs[tenant][doc_id]
    return {"deleted": doc_id}


# ── Built-in test harness ─────────────────────────────────────────────────────
if __name__ == "__main__":
    RESET = "\033[0m"; GREEN = "\033[32m"; RED = "\033[31m"
    CYAN  = "\033[36m"; BOLD  = "\033[1m"; DIM  = "\033[2m"

    results = []
    def check(name, passed, detail=""):
        results.append((name, passed))
        tag = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  [{tag}]  {BOLD}{name}{RESET}  {DIM}{detail}{RESET}")

    client = TestClient(app, raise_server_exceptions=False)

    print(f"\n{BOLD}{CYAN}Document Service — Developer Test Suite{RESET}")
    print(f"{CYAN}{'='*50}{RESET}\n")

    # ── Auth scenarios ────────────────────────────────────────────────────────
    print(f"{BOLD}Auth scenarios{RESET}")

    r = client.get("/documents")
    check("No token → 401", r.status_code == 401,
          r.json().get("detail", r.json().get("title", "")))

    r = client.get("/documents", headers={"Authorization": "Bearer revoked-token"})
    check("Revoked token → 401", r.status_code in (401, 403),
          str(r.json())[:60])

    r = client.get("/healthz")
    check("Health endpoint bypasses auth", r.status_code == 200, str(r.json()))

    # ── Alice (admin) scenarios ───────────────────────────────────────────────
    print(f"\n{BOLD}Alice — admin + user roles{RESET}")
    ALICE = {"Authorization": "Bearer alice-token"}

    r = client.get("/documents", headers=ALICE)
    check("Alice can list documents", r.status_code == 200,
          f"tenant={r.json()['tenant']}  count={len(r.json()['documents'])}")

    r = client.get("/documents/doc-1", headers=ALICE)
    check("Alice can read doc-1", r.status_code == 200,
          f"title={r.json()['title']}")

    r = client.post("/documents",
                    json={"title": "New Report", "content": "Q1 2025"},
                    headers=ALICE)
    check("Alice can create a document (user role)", r.status_code == 200,
          f"created={r.json().get('created')}")

    r = client.delete("/documents/doc-2", headers=ALICE)
    check("Alice can delete a document (admin role)", r.status_code == 200,
          f"deleted={r.json().get('deleted')}")

    r = client.get("/documents/doc-2", headers=ALICE)
    check("Deleted doc-2 → 404", r.status_code == 404,
          r.json()["detail"]["detail"])

    # ── Carol (viewer) scenarios ──────────────────────────────────────────────
    print(f"\n{BOLD}Carol — viewer role only{RESET}")
    CAROL = {"Authorization": "Bearer carol-token"}

    r = client.get("/documents", headers=CAROL)
    check("Carol can list documents (viewer)", r.status_code == 200,
          f"user={r.json()['user']}")

    r = client.get("/documents/doc-1", headers=CAROL)
    check("Carol can read doc-1 (viewer)", r.status_code == 200,
          f"title={r.json()['title']}")

    r = client.post("/documents",
                    json={"title": "Attempt", "content": "..."},
                    headers=CAROL)
    check("Carol cannot create (needs user role) → 403", r.status_code == 403,
          str(r.json().get("detail", ""))[:60])

    r = client.delete("/documents/doc-1", headers=CAROL)
    check("Carol cannot delete (needs admin role) → 403", r.status_code == 403,
          str(r.json().get("detail", ""))[:60])

    # ── Not found ─────────────────────────────────────────────────────────────
    print(f"\n{BOLD}Error handling{RESET}")

    r = client.get("/documents/doc-999", headers=ALICE)
    check("Unknown doc → 404 RFC 9457", r.status_code == 404,
          r.json()["detail"].get("detail", ""))

    # ── Summary ───────────────────────────────────────────────────────────────
    passed = sum(1 for _, ok in results if ok)
    total  = len(results)
    colour = GREEN if passed == total else RED
    print(f"\n{colour}{BOLD}{passed}/{total} passed{RESET}\n")
    sys.exit(0 if passed == total else 1)
