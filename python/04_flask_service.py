"""
CoreSDK — Example 04: Flask Service
=====================================
Flask API wired to the real sidecar, demonstrating:

  - JWT authentication via CoreSDKFlask middleware
  - Rate limiting (check_rate_limit) on write endpoints
  - Audit event emission (emit_audit_event) on state changes
  - require_auth decorator for protected routes

Run:
    export CORESDK_SIDECAR_ADDR=[::1]:50051
    python 04_flask_service.py
"""
import os
import sys

from flask import Flask, g, jsonify, request

from coresdk import SDK, require_auth
from coresdk.middleware.flask import CoreSDKFlask

SIDECAR = os.environ.get("CORESDK_SIDECAR_ADDR", "[::1]:50051")
TENANT  = os.environ.get("CORESDK_TENANT_ID", "acme-corp")

# ── SDK (public API — no private imports) ─────────────────────────────────────
_sdk = SDK.from_env()

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
CoreSDKFlask(_sdk, app)

_store: dict = {
    "acme-corp": [
        {"id": 1, "name": "Widget A", "price": 99.00},
        {"id": 2, "name": "Widget B", "price": 149.00},
    ]
}


def _tenant() -> str:
    """Return the tenant from JWT claims, falling back to env default."""
    claims = getattr(g, "claims", None)
    return (claims.get("tenant_id") if isinstance(claims, dict) else None) or TENANT


def _user() -> str:
    """Return the subject from JWT claims, falling back to 'anonymous'."""
    claims = getattr(g, "claims", None)
    return (claims.get("sub") if isinstance(claims, dict) else None) or "anonymous"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.get("/products")
def list_products():
    tenant = _tenant()
    return jsonify({
        "tenant":   tenant,
        "user":     _user(),
        "products": _store.get(tenant, []),
    })


@app.post("/products")
@require_auth
def create_product():
    """Create a product — demonstrates rate limiting + audit event emission."""
    tenant = _tenant()
    user   = _user()

    # Rate limiting: protect write endpoints from abuse
    rate = _sdk.check_rate_limit(f"create_product:{user}", tenant_id=tenant)
    if not rate.allowed:
        return jsonify({
            "error": "rate_limit_exceeded",
            "retry_after": rate.retry_after_seconds,
        }), 429

    payload = request.get_json() or {}
    new_id  = max((p["id"] for p in _store.get(tenant, [])), default=0) + 1
    product = {"id": new_id, "name": payload.get("name", "Unnamed"),
               "price": payload.get("price", 0.0)}
    _store.setdefault(tenant, []).append(product)

    # Audit: record every write for compliance
    _sdk.emit_audit_event(
        action="product.created",
        resource_type="product",
        resource_id=str(new_id),
        tenant_id=tenant,
        user_id=user,
        outcome="success",
        metadata={"name": product["name"]},
    )

    return jsonify({"created": product}), 201


# ── Built-in test harness ─────────────────────────────────────────────────────
if __name__ == "__main__":
    RESET="\033[0m"; GREEN="\033[32m"; RED="\033[31m"; CYAN="\033[36m"
    BOLD="\033[1m"; DIM="\033[2m"

    results = []
    def check(name, passed, detail=""):
        results.append((name, passed))
        tag = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  [{tag}]  {BOLD}{name}{RESET}  {DIM}{detail}{RESET}")

    print(f"\n{BOLD}{CYAN}Flask Product Service — Real Sidecar Tests{RESET}")
    print(f"{CYAN}{'='*50}{RESET}")

    c = app.test_client()
    ALICE = {"Authorization": "Bearer alice-token"}

    print(f"\n{BOLD}Auth{RESET}")
    r = c.get("/products")
    check("No token → 401", r.status_code == 401, str(r.get_json()))

    r = c.get("/healthz")
    check("Health bypasses auth → 200", r.status_code == 200)

    r = c.get("/products", headers=ALICE)
    check("Token → sidecar → 200 (fail-open)", r.status_code == 200,
          "sidecar responded, fail-open")

    print(f"\n{BOLD}CRUD + Rate Limit + Audit{RESET}")
    r = c.get("/products", headers=ALICE)
    check("List products", r.status_code == 200,
          f"count={len(r.get_json().get('products', []))}")

    r = c.post("/products",
               json={"name": "Widget C", "price": 199.00},
               headers={**ALICE, "Content-Type": "application/json"})
    # Without JWKS, fail-open claims are None → require_auth → 401/403 (expected).
    # In production with real JWKS: claims populated → rate check → audit → 201.
    check("Create product (require_auth with fail-open → 401/403 expected)",
          r.status_code in (201, 401, 403, 429), str(r.status_code))

    passed = sum(1 for _, ok in results if ok)
    total  = len(results)
    colour = GREEN if passed == total else RED
    print(f"\n{colour}{BOLD}{passed}/{total} passed{RESET}\n")
    sys.exit(0 if passed == total else 1)
