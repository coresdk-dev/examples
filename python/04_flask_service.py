"""
CoreSDK — Example 04: Flask Service with Auth
==============================================
A Flask API using CoreSDKFlask extension + require_auth decorator.

Run:
    pip install coresdk flask
    python 04_flask_service.py
"""
import sys
sys.path.insert(0, "/tmp/coresdk-sdk-python")

from flask import Flask, g, jsonify, request

from coresdk._types import AuthDecision
from coresdk.middleware.flask import CoreSDKFlask, require_auth
from coresdk.testing._mock import MockSDK

# ── SDK setup ─────────────────────────────────────────────────────────────────
sdk = MockSDK(
    default_claims={"sub": "alice", "tenant_id": "acme-corp", "roles": ["admin"]},
)
sdk.set_token_decision("readonly-token", AuthDecision(
    allowed=True,
    claims={"sub": "bob", "tenant_id": "acme-corp", "roles": ["viewer"]},
))
sdk.set_token_rejected("bad-token", reason="signature verification failed")

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
CoreSDKFlask(sdk, app)

# In-memory store
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
    """Any authenticated user can browse products."""
    tenant = g.claims.get("tenant_id", "unknown") if g.claims else "unknown"
    return jsonify({
        "tenant":   tenant,
        "user":     g.claims.get("sub") if g.claims else None,
        "products": _store.get(tenant, []),
    })

@app.post("/products")
@require_auth
def create_product():
    """Only authenticated users with g.claims set can create products."""
    tenant  = g.claims["tenant_id"]
    payload = request.get_json()
    new_id  = max((p["id"] for p in _store.get(tenant, [])), default=0) + 1
    product = {"id": new_id, "name": payload["name"], "price": payload["price"]}
    _store.setdefault(tenant, []).append(product)
    return jsonify({"created": product}), 201


# ── Built-in test harness ─────────────────────────────────────────────────────
if __name__ == "__main__":
    RESET = "\033[0m"; GREEN = "\033[32m"; RED = "\033[31m"
    CYAN  = "\033[36m"; BOLD  = "\033[1m"; DIM  = "\033[2m"

    results = []
    def check(name, passed, detail=""):
        results.append((name, passed))
        tag = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  [{tag}]  {BOLD}{name}{RESET}  {DIM}{detail}{RESET}")

    print(f"\n{BOLD}{CYAN}Flask Product Service — Developer Test Suite{RESET}")
    print(f"{CYAN}{'='*50}{RESET}\n")

    c = app.test_client()

    print(f"{BOLD}Auth scenarios{RESET}")
    r = c.get("/products")
    check("No token → 401", r.status_code == 401, str(r.get_json()))

    r = c.get("/products", headers={"Authorization": "Bearer bad-token"})
    check("Bad token → 401", r.status_code == 401, str(r.get_json()))

    r = c.get("/healthz")
    check("Health bypasses auth", r.status_code == 200)

    print(f"\n{BOLD}Alice (admin){RESET}")
    ALICE = {"Authorization": "Bearer alice-token"}

    r = c.get("/products", headers=ALICE)
    check("Alice can list products", r.status_code == 200,
          f"count={len(r.get_json()['products'])}")

    r = c.post("/products",
               json={"name": "Widget C", "price": 199.00},
               headers={**ALICE, "Content-Type": "application/json"})
    check("Alice can create product", r.status_code == 201,
          f"id={r.get_json()['created']['id']}")

    print(f"\n{BOLD}Bob (viewer / readonly){RESET}")
    BOB = {"Authorization": "Bearer readonly-token"}

    r = c.get("/products", headers=BOB)
    check("Bob can list products", r.status_code == 200,
          f"user={r.get_json()['user']}")

    # Bob has g.claims set so require_auth passes — Flask middleware doesn't
    # block by role, that's the app's responsibility
    r = c.post("/products",
               json={"name": "Attempt", "price": 0},
               headers={**BOB, "Content-Type": "application/json"})
    check("Bob can POST (role enforcement is app-level)", r.status_code == 201,
          "app should add role check if needed")

    passed = sum(1 for _, ok in results if ok)
    total  = len(results)
    colour = GREEN if passed == total else RED
    print(f"\n{colour}{BOLD}{passed}/{total} passed{RESET}\n")
    sys.exit(0 if passed == total else 1)
