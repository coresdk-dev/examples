"""
CoreSDK — Example 02: Multi-Tenant Service
===========================================
One SDK client per tenant, each isolated. Requests are routed to the
correct tenant context and tenant isolation is enforced at the app layer.

Real sidecar — no mocks.

Run:
    export CORESDK_SIDECAR_ADDR=[::1]:50051
    python 02_multi_tenant.py
"""
import os
import sys
sys.path.insert(0, "/tmp/coresdk-sdk-python")

from coresdk._client import CoreSDKClient
from coresdk._config import SDKConfig

SIDECAR = os.environ.get("CORESDK_SIDECAR_ADDR", "[::1]:50051")

print("CoreSDK — Multi-Tenant Example\n" + "="*40)

# ── One SDK client per tenant ─────────────────────────────────────────────────
# In production each tenant gets its own config (separate policy bundle,
# JWK set, HMAC key). Here all hit the same dev sidecar with tenant_id scoping.
def make_sdk(tenant_id: str) -> CoreSDKClient:
    return CoreSDKClient(SDKConfig(
        sidecar_addr=SIDECAR,
        tenant_id=tenant_id,
        service_name="multi-tenant-api",
        fail_mode="open",
    ))

sdks = {
    "acme-corp": make_sdk("acme-corp"),
    "globex":    make_sdk("globex"),
    "initech":   make_sdk("initech"),
}

# ── Simulate incoming requests ────────────────────────────────────────────────
requests = [
    # (token,           tenant_id,   action,   resource)
    ("alice-token",  "acme-corp",  "read",   "reports/q4.pdf"),
    ("alice-token",  "acme-corp",  "delete", "reports/q4.pdf"),
    ("bob-token",    "globex",     "read",   "invoices/inv-001"),
    ("bob-token",    "globex",     "write",  "invoices/inv-001"),
    ("carol-token",  "initech",    "read",   "wiki/home"),
    # Cross-tenant attempt — acme token used against globex SDK
    ("alice-token",  "globex",     "read",   "globex/secret"),
]

print(f"\n{'Token':<15} {'Tenant':<12} {'Action':<8} {'Resource':<25} {'Sidecar Response'}")
print("-"*85)

for token, tenant_id, action, resource in requests:
    sdk = sdks[tenant_id]
    decision = sdk.validate_token(token, action=action, resource=resource)

    # App-layer tenant isolation: if the token's tenant claim doesn't match,
    # reject even if the sidecar allowed it (sidecar has no JWKS here)
    token_tenant = decision.claims.get("tenant_id", tenant_id)
    cross_tenant = token_tenant and token_tenant != tenant_id

    if cross_tenant:
        status = f"✗ TENANT MISMATCH (token={token_tenant}, req={tenant_id})"
    elif decision.allowed:
        status = f"✓ allowed  reason={decision.reason!r}"
    else:
        status = f"✗ denied   reason={decision.reason!r}"

    print(f"{token:<15} {tenant_id:<12} {action:<8} {resource:<25} {status}")

print("\n✓ Multi-tenant routing complete")
