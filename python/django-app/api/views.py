"""
CoreSDK — Django REST Framework App Example
============================================
Implements all CoreSDK features matching the fastapi-app:

  - JWT authentication via CoreSDKMiddleware
  - Role-based access control (require_role decorator)
  - Multi-tenant isolation (tenant-scoped data)
  - OPA/Rego policy enforcement (evaluate_policy)
  - PII-safe OpenTelemetry tracing (@trace)
  - RFC 9457 structured error responses
  - Config from coresdk.toml + env var overrides
"""

import functools
import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from coresdk import CoreSDKClient, SDKConfig
from coresdk.tracing.decorator import trace

# ── SDK client ────────────────────────────────────────────────────────────────

_cfg = settings.CORESDK
_sdk_cfg = _cfg["sdk"]
TENANTS: dict = _cfg["tenants"]

_sdk = CoreSDKClient(
    SDKConfig(
        sidecar_addr=_sdk_cfg["sidecar_addr"],
        tenant_id=_sdk_cfg["tenant_id"],
        service_name=_sdk_cfg["service_name"],
        fail_mode=_sdk_cfg["fail_mode"],
        dev_mode=_sdk_cfg["dev_mode"],
    )
)

# ── In-memory store (replace with your DB) ────────────────────────────────────

_db: dict[str, list[dict]] = {
    "acme-corp": [
        {"id": 1, "name": "Widget A", "price": 99.00, "owner": "alice"},
        {"id": 2, "name": "Widget B", "price": 149.00, "owner": "alice"},
    ],
    "globex": [
        {"id": 1, "name": "Gadget X", "price": 299.00, "owner": "bob"},
    ],
}

# ── Helpers ───────────────────────────────────────────────────────────────────


def _current_user(request) -> dict:
    """Extract JWT claims set by CoreSDKMiddleware (stored as request.coresdk_claims)."""
    claims = getattr(request, "coresdk_claims", None)
    if isinstance(claims, dict):
        return claims
    # fail-open: sidecar allowed but no real JWT — use tenant default
    return {"sub": "anonymous", "roles": [], "tenant_id": _sdk_cfg["tenant_id"]}


def _get_tenant(request) -> str:
    return _current_user(request).get("tenant_id") or _sdk_cfg["tenant_id"]


def _problem(status: int, title: str, detail: str, type_: str = None) -> JsonResponse:
    """Return an RFC 9457 Problem Detail response."""
    body = {
        "type": type_ or f"https://coresdk.io/errors/{title.lower().replace(' ', '-')}",
        "title": title,
        "status": status,
        "detail": detail,
    }
    return JsonResponse(body, status=status, content_type="application/problem+json")


def require_role(role: str):
    """Decorator: return 403 if the authenticated user lacks `role`."""

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = _current_user(request)
            if role not in user.get("roles", []):
                return _problem(
                    403,
                    "Forbidden",
                    f"Role '{role}' required. Your roles: {user.get('roles', [])}",
                    type_="https://coresdk.io/errors/forbidden",
                )
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


# ── Routes ────────────────────────────────────────────────────────────────────


@require_http_methods(["GET"])
def healthz(request):
    """Health check — bypasses auth (exempt in CoreSDKMiddleware.EXEMPT_PATHS)."""
    return JsonResponse({"status": "ok", "service": _sdk_cfg["service_name"]})


@require_http_methods(["GET"])
@trace(intent="get-current-user")
def me(request):
    """Return the authenticated user's JWT claims."""
    return JsonResponse(_current_user(request))


@trace(intent="list-products")
@require_http_methods(["GET", "POST"])
def products(request):
    """
    GET  /products — list products scoped to the authenticated user's tenant.
    POST /products — create a product; requires 'editor' role.
    """
    if request.method == "GET":
        return _list_products(request)
    return _create_product(request)


def _list_products(request):
    tenant = _get_tenant(request)
    user = _current_user(request)
    return JsonResponse(
        {
            "tenant": tenant,
            "user": user.get("sub"),
            "products": _db.get(tenant, []),
        }
    )


@require_role("editor")
def _create_product(request):
    tenant = _get_tenant(request)
    user = _current_user(request)
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _problem(400, "Bad Request", "Request body must be valid JSON.")
    items = _db.setdefault(tenant, [])
    new_id = max((p["id"] for p in items), default=0) + 1
    product = {
        "id": new_id,
        "name": body.get("name", "Unnamed"),
        "price": body.get("price", 0.0),
        "owner": user.get("sub", "unknown"),
    }
    items.append(product)
    return JsonResponse({"created": product}, status=201)


@require_http_methods(["GET", "DELETE"])
@trace(intent="get-product")
def product_detail(request, pk: int):
    """
    GET    /products/<pk> — get a single product (RFC 9457 404 if missing).
    DELETE /products/<pk> — delete a product; requires 'admin' role.
    """
    if request.method == "GET":
        return _get_product(request, pk)
    return _delete_product(request, pk)


def _get_product(request, pk: int):
    tenant = _get_tenant(request)
    products = _db.get(tenant, [])
    product = next((p for p in products if p["id"] == pk), None)
    if not product:
        return _problem(
            404,
            "Not Found",
            f"Product {pk} not found in tenant '{tenant}'",
            type_="https://coresdk.io/errors/not-found",
        )
    return JsonResponse(product)


@require_role("admin")
def _delete_product(request, pk: int):
    tenant = _get_tenant(request)
    products = _db.get(tenant, [])
    product = next((p for p in products if p["id"] == pk), None)
    if not product:
        return _problem(
            404,
            "Not Found",
            f"Product {pk} not found",
            type_="https://coresdk.io/errors/not-found",
        )
    _db[tenant] = [p for p in products if p["id"] != pk]
    return JsonResponse({"deleted": pk})


@require_http_methods(["GET"])
@trace(intent="policy-check")
def policy_check(request):
    """
    GET /policy/check?action=X&resource=Y
    Evaluate a Rego policy rule — shows how to call evaluate_policy() directly.
    """
    action = request.GET.get("action", "")
    resource = request.GET.get("resource", "")
    user = _current_user(request)
    tenant = _get_tenant(request)

    result = _sdk.evaluate_policy(
        "data.authz.allow",
        {
            "tenant_id": tenant,
            "subject": user.get("sub"),
            "action": action,
            "resource": resource,
            "context": {"roles": user.get("roles", [])},
        },
    )
    return JsonResponse(
        {
            "tenant": tenant,
            "subject": user.get("sub"),
            "action": action,
            "resource": resource,
            "allowed": result,
        }
    )


@require_http_methods(["GET"])
@trace(intent="rate-limit-status")
def rate_limit_status(request):
    """
    GET /rate-limit?key=<key>
    Check a rate limit for the authenticated user.

    Shows how to call check_rate_limit() directly for per-user or per-endpoint
    throttling without blocking the request — useful for surfacing quota info to
    the client (e.g. X-RateLimit-* headers) or for soft-limiting expensive ops.

    Example:
        curl -H "Authorization: Bearer <token>" \
             "http://localhost:8000/rate-limit?key=search"
    """
    key = request.GET.get("key", "default")
    user = _current_user(request)
    tenant = _get_tenant(request)

    # Construct a per-user, per-key rate-limit identifier
    rate_key = f"{key}:{user.get('sub', 'anonymous')}"
    rate = _sdk.check_rate_limit(rate_key, tenant_id=tenant)

    return JsonResponse(
        {
            "tenant": tenant,
            "subject": user.get("sub"),
            "key": rate_key,
            "allowed": rate.allowed,
            "remaining": rate.remaining,
            "retry_after_seconds": rate.retry_after_seconds,
        },
        status=200 if rate.allowed else 429,
    )
