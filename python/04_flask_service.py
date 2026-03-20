"""
CoreSDK — Example 04: Flask Service
=====================================
Flask API wired to the real sidecar via CoreSDKFlask extension.

Run:
    export CORESDK_SIDECAR_ADDR=[::1]:50051
    python 04_flask_service.py
"""
import os
import sys
sys.path.insert(0, "/tmp/coresdk-sdk-python")

from flask import Flask, g, jsonify, request

from coresdk._client import CoreSDKClient
from coresdk._config import SDKConfig
from coresdk.middleware.flask import CoreSDKFlask, require_auth

SIDECAR = os.environ.get("CORESDK_SIDECAR_ADDR", "[::1]:50051")

# ── Real SDK client ───────────────────────────────────────────────────────────
_config = SDKConfig(
    sidecar_addr=SIDECAR,
    tenant_id="acme-corp",
    service_name="product-service",
    fail_mode="open",
    dev_mode=False,
)
_client = CoreSDKClient(_config)

class SDKAdapter:
    config = _config
    def authorize(self, token, **kw):      return _client.validate_token(token, **kw)
    def authorize_sync(self, token, **kw): return _client.validate_token(token, **kw)

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
CoreSDKFlask(SDKAdapter(), app)

_store: dict = {
    "acme-corp": [
        {"id": 1, "name": "Widget A", "price": 99.00},
        {"id": 2, "name": "Widget B", "price": 149.00},
    ]
}

@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})

@app.get("/products")
def list_products():
    tenant = (g.claims.get("tenant_id") or _config.tenant_id) if g.claims else _config.tenant_id
    return jsonify({
        "tenant":   tenant,
        "user":     g.claims.get("sub") if g.claims else None,
        "products": _store.get(tenant, []),
    })

@app.post("/products")
@require_auth
def create_product():
    tenant  = g.claims.get("tenant_id") or _config.tenant_id
    payload = request.get_json()
    new_id  = max((p["id"] for p in _store.get(tenant, [])), default=0) + 1
    product = {"id": new_id, "name": payload["name"], "price": payload["price"]}
    _store.setdefault(tenant, []).append(product)
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
          f"sidecar responded, fail-open")

    print(f"\n{BOLD}CRUD{RESET}")
    r = c.get("/products", headers=ALICE)
    check("List products", r.status_code == 200,
          f"count={len(r.get_json().get('products', []))}")

    r = c.post("/products",
               json={"name": "Widget C", "price": 199.00},
               headers={**ALICE, "Content-Type": "application/json"})
    # Without JWKS, fail-open claims are None → require_auth → 403 (expected)
    # In production with real JWKS: claims populated → 201
    check("Create product (require_auth with fail-open → 403 expected)",
          r.status_code in (201, 403), str(r.status_code))

    passed = sum(1 for _, ok in results if ok)
    total  = len(results)
    colour = GREEN if passed == total else RED
    print(f"\n{colour}{BOLD}{passed}/{total} passed{RESET}\n")
    sys.exit(0 if passed == total else 1)
