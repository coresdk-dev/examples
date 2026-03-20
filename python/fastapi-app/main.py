"""
CoreSDK — FastAPI App Example
==============================
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
    pip install "coresdk[fastapi]" uvicorn
    uvicorn main:app --reload

    # Test (no token → 401)
    curl http://localhost:8000/products

    # Test (with token → 200, fail-open without real JWKS)
    curl -H "Authorization: Bearer alice-token" http://localhost:8000/products
"""
import os
import tomllib
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from coresdk import CoreSDKClient, SDKConfig
from coresdk.middleware.fastapi import CoreSDKMiddleware
from coresdk.tracing.decorator import trace
from coresdk.errors._rfc9457 import ProblemDetailError

# ── Load config ───────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load coresdk.toml, with env var overrides."""
    config_path = Path(__file__).parent / "coresdk.toml"
    with open(config_path, "rb") as f:
        cfg = tomllib.load(f)
    # Allow env var overrides for any sdk.* key
    sdk = cfg["sdk"]
    sdk["sidecar_addr"]  = os.getenv("CORESDK_SIDECAR_ADDR",  sdk["sidecar_addr"])
    sdk["tenant_id"]     = os.getenv("CORESDK_TENANT_ID",     sdk["tenant_id"])
    sdk["service_name"]  = os.getenv("CORESDK_SERVICE_NAME",  sdk["service_name"])
    sdk["fail_mode"]     = os.getenv("CORESDK_FAIL_MODE",     sdk["fail_mode"])
    sdk["dev_mode"]      = os.getenv("CORESDK_DEV_MODE", str(sdk["dev_mode"])).lower() == "true"
    return cfg

cfg = load_config()
sdk_cfg = cfg["sdk"]
TENANTS: dict = cfg["tenants"]

# ── SDK client ────────────────────────────────────────────────────────────────

_sdk = CoreSDKClient(SDKConfig(
    sidecar_addr = sdk_cfg["sidecar_addr"],
    tenant_id    = sdk_cfg["tenant_id"],
    service_name = sdk_cfg["service_name"],
    fail_mode    = sdk_cfg["fail_mode"],
    dev_mode     = sdk_cfg["dev_mode"],
))

class SDKAdapter:
    """Thin adapter — middleware expects .authorize() and .config."""
    config = _sdk.config
    def authorize(self, token, **kw):      return _sdk.validate_token(token, **kw)
    def authorize_sync(self, token, **kw): return _sdk.validate_token(token, **kw)

# ── App setup ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"  sidecar : {sdk_cfg['sidecar_addr']}")
    print(f"  tenant  : {sdk_cfg['tenant_id']}")
    print(f"  service : {sdk_cfg['service_name']}")
    print(f"  tenants : {list(TENANTS.keys())}")
    yield

app = FastAPI(
    title="Product API",
    version=cfg["observability"]["service_version"],
    description="CoreSDK example — auth, policy, tracing, multi-tenancy",
    lifespan=lifespan,
)

# Register CoreSDK middleware — every route protected by default
app.add_middleware(
    CoreSDKMiddleware,
    sdk=SDKAdapter(),
    exclude_paths=["/healthz", "/docs", "/openapi.json", "/redoc"],
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def current_user(request: Request) -> dict:
    """Extract JWT claims set by CoreSDKMiddleware."""
    user = getattr(request.state, "coresdk_user", None)
    if isinstance(user, dict):
        return user
    # fail-open: sidecar allowed but no real JWT — use tenant default
    return {"sub": "anonymous", "roles": [], "tenant_id": sdk_cfg["tenant_id"]}

def get_tenant(request: Request) -> str:
    return current_user(request).get("tenant_id") or sdk_cfg["tenant_id"]

def require_role(role: str):
    """Dependency: raise 403 if the authenticated user lacks `role`."""
    def _check(request: Request):
        user = current_user(request)
        if role not in user.get("roles", []):
            raise HTTPException(status_code=403, detail={
                "type":   "https://coresdk.io/errors/forbidden",
                "title":  "Forbidden",
                "status": 403,
                "detail": f"Role '{role}' required. Your roles: {user.get('roles', [])}",
            })
        return user
    return Depends(_check)

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

@app.get("/healthz", tags=["ops"])
async def healthz():
    """Health check — bypasses auth."""
    return {"status": "ok", "service": sdk_cfg["service_name"]}


@app.get("/me", tags=["auth"])
@trace(intent="get-current-user")
async def me(request: Request):
    """Return the authenticated user's JWT claims."""
    return current_user(request)


@app.get("/tenants", tags=["admin"])
@trace(intent="list-tenants")
async def list_tenants(_=require_role("admin")):
    """Admin only — list all configured tenants."""
    return {"tenants": [
        {"slug": slug, **info} for slug, info in TENANTS.items()
    ]}


@app.get("/products", tags=["products"])
@trace(intent="list-products")
async def list_products(request: Request):
    """List products scoped to the authenticated user's tenant."""
    tenant = get_tenant(request)
    user   = current_user(request)
    return {
        "tenant":   tenant,
        "user":     user.get("sub"),
        "products": _db.get(tenant, []),
    }


@app.get("/products/{product_id}", tags=["products"])
@trace(intent="get-product")
async def get_product(product_id: int, request: Request):
    """Get a single product — scoped to the caller's tenant."""
    tenant   = get_tenant(request)
    products = _db.get(tenant, [])
    product  = next((p for p in products if p["id"] == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail={
            "type":   "https://coresdk.io/errors/not-found",
            "title":  "Not Found",
            "status": 404,
            "detail": f"Product {product_id} not found in tenant '{tenant}'",
        })
    return product


@app.post("/products", tags=["products"], status_code=201)
@trace(intent="create-product")
async def create_product(body: dict, request: Request, _=require_role("editor")):
    """Create a product — requires 'editor' role."""
    tenant = get_tenant(request)
    user   = current_user(request)
    items  = _db.setdefault(tenant, [])
    new_id = max((p["id"] for p in items), default=0) + 1
    product = {
        "id":    new_id,
        "name":  body.get("name", "Unnamed"),
        "price": body.get("price", 0.0),
        "owner": user.get("sub", "unknown"),
    }
    items.append(product)
    return {"created": product}


@app.delete("/products/{product_id}", tags=["products"])
@trace(intent="delete-product")
async def delete_product(product_id: int, request: Request, _=require_role("admin")):
    """Delete a product — requires 'admin' role."""
    tenant   = get_tenant(request)
    products = _db.get(tenant, [])
    product  = next((p for p in products if p["id"] == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail={
            "type":   "https://coresdk.io/errors/not-found",
            "title":  "Not Found",
            "status": 404,
            "detail": f"Product {product_id} not found",
        })
    _db[tenant] = [p for p in products if p["id"] != product_id]
    return {"deleted": product_id}


@app.get("/policy/check", tags=["policy"])
@trace(intent="policy-check")
async def policy_check(action: str, resource: str, request: Request):
    """
    Evaluate a Rego policy rule directly.
    Shows how to call evaluate_policy() from your own business logic.
    """
    user   = current_user(request)
    tenant = get_tenant(request)
    result = _sdk.evaluate_policy("data.authz.allow", {
        "tenant_id": tenant,
        "subject":   user.get("sub"),
        "action":    action,
        "resource":  resource,
        "context":   {"roles": user.get("roles", [])},
    })
    return {
        "tenant":   tenant,
        "subject":  user.get("sub"),
        "action":   action,
        "resource": resource,
        "allowed":  result,
    }


# ── RFC 9457 error handler ────────────────────────────────────────────────────

@app.exception_handler(ProblemDetailError)
async def problem_detail_handler(request: Request, exc: ProblemDetailError):
    return JSONResponse(status_code=exc.status, content=exc.to_dict(),
                        media_type="application/problem+json")
