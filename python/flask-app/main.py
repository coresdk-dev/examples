"""
CoreSDK — Flask App Example
============================
A complete multi-tenant REST API demonstrating every CoreSDK feature:

  ✓ JWT authentication via CoreSDK sidecar
  ✓ Role-based access control (require_role)
  ✓ Multi-tenant isolation (tenant-scoped data)
  ✓ OPA/Rego policy enforcement
  ✓ PII-safe OpenTelemetry tracing (@trace)
  ✓ RFC 9457 structured error responses
  ✓ Config from coresdk.toml + env var overrides

Run:
    # Terminal 1 — start sidecar
    coresdk-sidecar

    # Terminal 2 — start API
    pip install "coresdk[flask]" gunicorn
    flask --app main run --port 5000

    # Test (no token → 401)
    curl http://localhost:5000/products

    # Test (with token → 200, fail-open without real JWKS)
    curl -H "Authorization: Bearer alice-token" http://localhost:5000/products
"""
import os
import tomllib
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, request

from coresdk import CoreSDKClient, SDKConfig
from coresdk.errors import ProblemDetailError
from coresdk.middleware.flask import CoreSDKMiddleware
from coresdk.tracing.decorator import trace

# ── Load config ───────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load coresdk.toml, with env var overrides."""
    config_path = Path(__file__).parent / "coresdk.toml"
    with open(config_path, "rb") as f:
        cfg = tomllib.load(f)
    sdk = cfg["sdk"]
    sdk["sidecar_addr"]  = os.getenv("CORESDK_SIDECAR_ADDR",  sdk["sidecar_addr"])
    sdk["tenant_id"]     = os.getenv("CORESDK_TENANT_ID",     sdk["tenant_id"])
    sdk["service_name"]  = os.getenv("CORESDK_SERVICE_NAME",  sdk["service_name"])
    sdk["fail_mode"]     = os.getenv("CORESDK_FAIL_MODE",     sdk["fail_mode"])
    sdk["dev_mode"]      = os.getenv("CORESDK_DEV_MODE", str(sdk["dev_mode"])).lower() == "true"
    return cfg

_config_data = load_config()
_sdk_cfg     = _config_data["sdk"]
TENANTS: dict = _config_data["tenants"]

# ── SDK client ────────────────────────────────────────────────────────────────

_sdk = CoreSDKClient(SDKConfig(
    sidecar_addr = _sdk_cfg["sidecar_addr"],
    tenant_id    = _sdk_cfg["tenant_id"],
    service_name = _sdk_cfg["service_name"],
    fail_mode    = _sdk_cfg["fail_mode"],
    dev_mode     = _sdk_cfg["dev_mode"],
))

class SDKAdapter:
    """Thin adapter — Flask middleware expects .authorize_sync() and .config."""
    config = _sdk.config
    def authorize_sync(self, token, **kw): return _sdk.validate_token(token, **kw)

# ── App setup ─────────────────────────────────────────────────────────────────

app = Flask(__name__)
CoreSDKMiddleware(app, sdk=SDKAdapter(), exclude_paths=["/healthz"])

# ── Helpers ───────────────────────────────────────────────────────────────────

def current_user() -> dict:
    """Extract JWT claims set by CoreSDKMiddleware into Flask g."""
    claims = getattr(g, "claims", None)
    if isinstance(claims, dict):
        return claims
    # fail-open: sidecar allowed but no real JWT — return tenant default identity
    return {"sub": "anonymous", "roles": [], "tenant_id": _sdk_cfg["tenant_id"]}

def get_tenant() -> str:
    return current_user().get("tenant_id") or _sdk_cfg["tenant_id"]

def require_role(role: str):
    """Decorator: return 403 if the authenticated user lacks `role`."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = current_user()
            if role not in user.get("roles", []):
                return jsonify(ProblemDetailError(
                    type_uri="https://coresdk.io/errors/forbidden",
                    title="Forbidden",
                    status=403,
                    detail=f"Role '{role}' required. Your roles: {user.get('roles', [])}",
                ).to_dict()), 403, {"Content-Type": "application/problem+json"}
            return f(*args, **kwargs)
        return wrapper
    return decorator

def require_auth(f):
    """Decorator: require that the request was authenticated (not fail-open anonymous)."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not hasattr(g, "claims") or g.claims is None:
            return jsonify(ProblemDetailError(
                type_uri="https://coresdk.io/errors/unauthorized",
                title="Unauthorized",
                status=401,
                detail="Missing or invalid Authorization header.",
            ).to_dict()), 401, {"Content-Type": "application/problem+json"}
        return f(*args, **kwargs)
    return wrapper

# ── In-memory store (replace with your DB) ────────────────────────────────────

_db: dict[str, list[dict]] = {
    "acme-corp": [
        {"id": 1, "name": "Widget A", "price": 99.00,  "owner": "alice"},
        {"id": 2, "name": "Widget B", "price": 149.00, "owner": "alice"},
    ],
    "globex": [
        {"id": 1, "name": "Gadget X", "price": 299.00, "owner": "bob"},
    ],
}

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/healthz")
def healthz():
    """Health check — bypasses auth."""
    return jsonify({"status": "ok", "service": _sdk_cfg["service_name"]})


@app.get("/me")
@require_auth
@trace(intent="get-current-user")
def me():
    """Return the authenticated user's JWT claims."""
    return jsonify(current_user())


@app.get("/tenants")
@require_auth
@require_role("admin")
@trace(intent="list-tenants")
def list_tenants():
    """Admin only — list all configured tenants."""
    return jsonify({"tenants": [
        {"slug": slug, **info} for slug, info in TENANTS.items()
    ]})


@app.get("/products")
@require_auth
@trace(intent="list-products")
def list_products():
    """List products scoped to the authenticated user's tenant."""
    tenant = get_tenant()
    user   = current_user()
    return jsonify({
        "tenant":   tenant,
        "user":     user.get("sub"),
        "products": _db.get(tenant, []),
    })


@app.get("/products/<int:product_id>")
@require_auth
@trace(intent="get-product")
def get_product(product_id: int):
    """Get a single product — scoped to the caller's tenant."""
    tenant   = get_tenant()
    products = _db.get(tenant, [])
    product  = next((p for p in products if p["id"] == product_id), None)
    if not product:
        problem = ProblemDetailError(
            type_uri="https://coresdk.io/errors/not-found",
            title="Not Found",
            status=404,
            detail=f"Product {product_id} not found in tenant '{tenant}'",
        )
        return jsonify(problem.to_dict()), 404, {"Content-Type": "application/problem+json"}
    return jsonify(product)


@app.post("/products")
@require_auth
@require_role("editor")
@trace(intent="create-product")
def create_product():
    """Create a product — requires 'editor' role, enforces rate limit, emits audit event."""
    body   = request.get_json(force=True) or {}
    tenant = get_tenant()
    user   = current_user()

    # Rate limiting: prevent abuse of write endpoints
    rate = _sdk.check_rate_limit(f"create_product:{user.get('sub', '')}", tenant_id=tenant)
    if not rate.allowed:
        return jsonify({
            "type":   "https://coresdk.io/errors/rate-limited",
            "title":  "Too Many Requests",
            "status": 429,
            "detail": f"Rate limit exceeded. Retry after {rate.retry_after_seconds}s.",
        }), 429, {"Content-Type": "application/problem+json"}

    items  = _db.setdefault(tenant, [])
    new_id = max((p["id"] for p in items), default=0) + 1
    product = {
        "id":    new_id,
        "name":  body.get("name", "Unnamed"),
        "price": body.get("price", 0.0),
        "owner": user.get("sub", "unknown"),
    }
    items.append(product)

    # Audit: emit a tamper-evident record for every create
    _sdk.emit_audit_event(
        action="product.created",
        resource_type="product",
        resource_id=str(new_id),
        tenant_id=tenant,
        user_id=user.get("sub", "unknown"),
        outcome="success",
        metadata={"name": product["name"], "price": product["price"]},
    )

    return jsonify({"created": product}), 201


@app.delete("/products/<int:product_id>")
@require_auth
@require_role("admin")
@trace(intent="delete-product")
def delete_product(product_id: int):
    """Delete a product — requires 'admin' role."""
    tenant   = get_tenant()
    products = _db.get(tenant, [])
    product  = next((p for p in products if p["id"] == product_id), None)
    if not product:
        problem = ProblemDetailError(
            type_uri="https://coresdk.io/errors/not-found",
            title="Not Found",
            status=404,
            detail=f"Product {product_id} not found",
        )
        return jsonify(problem.to_dict()), 404, {"Content-Type": "application/problem+json"}
    _db[tenant] = [p for p in products if p["id"] != product_id]
    return jsonify({"deleted": product_id})


@app.get("/policy/check")
@require_auth
@trace(intent="policy-check")
def policy_check():
    """
    Evaluate a Rego policy rule directly.
    Shows how to call evaluate_policy() from your own business logic.
    """
    action   = request.args.get("action", "read")
    resource = request.args.get("resource", "")
    user     = current_user()
    tenant   = get_tenant()
    result = _sdk.evaluate_policy("data.authz.allow", {
        "tenant_id": tenant,
        "subject":   user.get("sub"),
        "action":    action,
        "resource":  resource,
        "context":   {"roles": user.get("roles", [])},
    })
    return jsonify({
        "tenant":   tenant,
        "subject":  user.get("sub"),
        "action":   action,
        "resource": resource,
        "allowed":  result,
    })


# ── RFC 9457 error handler ────────────────────────────────────────────────────

@app.errorhandler(ProblemDetailError)
def handle_problem_detail(exc: ProblemDetailError):
    return jsonify(exc.to_dict()), exc.status, {"Content-Type": "application/problem+json"}


if __name__ == "__main__":
    print(f"  sidecar : {_sdk_cfg['sidecar_addr']}")
    print(f"  tenant  : {_sdk_cfg['tenant_id']}")
    print(f"  tenants : {list(TENANTS.keys())}")
    app.run(debug=False, port=5000)
