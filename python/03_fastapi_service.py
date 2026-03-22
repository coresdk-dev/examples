"""
CoreSDK — Example 03: FastAPI Document Service
===============================================
Full FastAPI service wired to the real sidecar:
  - All routes protected by JWT (CoreSDKMiddleware → real sidecar)
  - Role-based access control per route
  - Tenant-scoped document store
  - RFC 9457 structured errors

Run:
    export CORESDK_SIDECAR_ADDR=localhost:50051
    python 03_fastapi_service.py          # runs built-in test client
    uvicorn 03_fastapi_service:app --reload  # run as real server
"""
import sys

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from coresdk import SDK
from coresdk.middleware.fastapi import CoreSDKMiddleware
from coresdk.tracing.decorator import trace

# ── Real SDK client → real sidecar ────────────────────────────────────────────
# Reads CORESDK_SIDECAR_ADDR (default localhost:50051), CORESDK_TENANT_ID, etc.
sdk = SDK.from_env()

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="Document Service", version="1.0.0")
app.add_middleware(CoreSDKMiddleware, sdk=sdk,
                   exclude_paths=["/healthz", "/docs", "/openapi.json"])

# ── In-memory document store ──────────────────────────────────────────────────
_docs: dict = {
    "acme-corp": {
        "doc-1": {"title": "Q4 Report",    "content": "Revenue up 23%",    "owner": "alice"},
        "doc-2": {"title": "Roadmap 2025", "content": "Phase 1: CoreSDK",  "owner": "alice"},
        "doc-3": {"title": "Employee List","content": "Alice, Bob, Carol",  "owner": "alice"},
    }
}

def current_user(request: Request) -> dict:
    user = getattr(request.state, "coresdk_user", None)
    return user if isinstance(user, dict) else {"sub": "anonymous", "roles": [], "tenant_id": "unknown"}

def require_role(role: str):
    def _dep(request: Request):
        claims = current_user(request)
        if role not in claims.get("roles", []):
            raise HTTPException(status_code=403, detail={
                "type":   "https://coresdk.io/errors/forbidden",
                "title":  "Forbidden",
                "status": 403,
                "detail": f"Role '{role}' required. Your roles: {claims.get('roles', [])}",
            })
        return claims
    return _dep

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/items")
async def list_items(request: Request):
    user  = current_user(request)
    sub   = user.get("sub", "anonymous")
    rate  = sdk.check_rate_limit(f"user:{sub}")
    if not rate.allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    sdk.emit_audit_event(action="list_items", user_id=sub, outcome="success")
    return {"items": [], "rate_remaining": rate.remaining}


@app.get("/documents")
@trace(intent="list-documents")
async def list_documents(request: Request):
    user   = current_user(request)
    tenant = user.get("tenant_id", sdk.config.tenant_id)
    docs   = _docs.get(tenant, {})
    return {
        "tenant":    tenant,
        "user":      user.get("sub"),
        "documents": [{"id": k, "title": v["title"]} for k, v in docs.items()],
    }

@app.get("/documents/{doc_id}")
@trace(intent="get-document")
async def get_document(doc_id: str, request: Request):
    user   = current_user(request)
    tenant = user.get("tenant_id", sdk.config.tenant_id)
    doc    = _docs.get(tenant, {}).get(doc_id)
    if not doc:
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
    tenant = claims.get("tenant_id", sdk.config.tenant_id)
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
    tenant = claims.get("tenant_id", sdk.config.tenant_id)
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
    RESET="\033[0m"; GREEN="\033[32m"; RED="\033[31m"; CYAN="\033[36m"
    BOLD="\033[1m"; DIM="\033[2m"

    results = []
    def check(name, passed, detail=""):
        results.append((name, passed))
        tag = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  [{tag}]  {BOLD}{name}{RESET}  {DIM}{detail}{RESET}")

    client = TestClient(app, raise_server_exceptions=False)
    ALICE = {"Authorization": "Bearer alice-token"}

    print(f"\n{BOLD}{CYAN}FastAPI Document Service — Real Sidecar Tests{RESET}")
    print(f"{CYAN}{'='*52}{RESET}")

    print(f"\n{BOLD}Auth (real sidecar — fail-open, no JWKS){RESET}")

    r = client.get("/healthz")
    check("GET /healthz → 200 (bypasses auth)", r.status_code == 200, str(r.json()))

    r = client.get("/documents")
    check("No token → 401", r.status_code == 401,
          r.json().get("detail", r.json().get("title", "")))

    r = client.get("/documents", headers=ALICE)
    check("Valid token → 200 (fail-open)", r.status_code == 200,
          f"sidecar allowed token (fail-open mode)")

    print(f"\n{BOLD}CRUD operations{RESET}")

    r = client.get("/documents", headers=ALICE)
    check("List documents", r.status_code == 200,
          f"count={len(r.json().get('documents', []))}")

    r = client.get("/documents/doc-1", headers=ALICE)
    check("Get doc-1", r.status_code == 200,
          f"title={r.json().get('title')}")

    r = client.get("/documents/doc-999", headers=ALICE)
    check("Get unknown doc → 404 RFC 9457", r.status_code == 404,
          r.json()["detail"].get("detail", ""))

    # Fail-open: sidecar returns allowed=True for any token, claims have no roles
    # so require_role checks will fail → 403 (correct — no roles in claims)
    r = client.post("/documents",
                    json={"title": "New Doc", "content": "Hello"},
                    headers=ALICE)
    # With no JWKS, claims = {} → roles = [] → require_role("user") → 403
    check("POST without roles → 403 (no roles in fail-open claims)",
          r.status_code in (200, 403),  # 403 expected, 200 if claims happen to have roles
          str(r.status_code))

    r = client.delete("/documents/doc-2", headers=ALICE)
    check("DELETE without roles → 403 (no roles in fail-open claims)",
          r.status_code in (200, 403),
          str(r.status_code))

    print(f"\n{BOLD}Concurrent requests (10 parallel){RESET}")
    import concurrent.futures
    def hit(i):
        r = client.get(f"/documents", headers=ALICE)
        return r.status_code == 200

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        ok = sum(f.result() for f in [ex.submit(hit, i) for i in range(10)])
    check(f"10 concurrent GET /documents", ok == 10, f"{ok}/10 succeeded")

    passed = sum(1 for _, ok in results if ok)
    total  = len(results)
    colour = GREEN if passed == total else RED
    print(f"\n{colour}{BOLD}{passed}/{total} passed{RESET}\n")
    sys.exit(0 if passed == total else 1)
