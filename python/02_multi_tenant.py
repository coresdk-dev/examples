"""
CoreSDK — Example 02: Multi-Tenant Service
===========================================
One SDK instance per tenant, each isolated. A request comes in with a
tenant_id claim in the JWT — route it to the right tenant context and
enforce per-tenant policy.

Real-world scenario:
  - SaaS app serving acme-corp, globex, and initech
  - Each tenant has its own policy rules
  - A user from acme-corp must NOT access globex data
  - Policy enforces tenant isolation automatically

Run:
    python 02_multi_tenant.py
"""
import sys
sys.path.insert(0, "/tmp/coresdk-sdk-python")

from coresdk._client import CoreSDKClient
from coresdk._config import SDKConfig
from coresdk._types import AuthDecision
from coresdk.testing._mock import MockSDK

print("CoreSDK — Multi-Tenant Example\n" + "="*40)

# ── Setup: one SDK client per tenant ─────────────────────────────────────────
# In production: SDKConfig(sidecar_addr="[::1]:50051", tenant_id=tenant_id)
# Here: MockSDK so the example runs without a sidecar

tenants = {
    "acme-corp": MockSDK(
        default_claims={"sub": "alice", "tenant_id": "acme-corp", "roles": ["admin"]},
    ),
    "globex": MockSDK(
        default_claims={"sub": "bob", "tenant_id": "globex", "roles": ["user"]},
    ),
    "initech": MockSDK(
        default_claims={"sub": "carol", "tenant_id": "initech", "roles": ["viewer"]},
    ),
}

# ── Simulate incoming requests ────────────────────────────────────────────────
requests = [
    # (token,            tenant_id,   action,   resource,           expected)
    ("token-alice",  "acme-corp",  "read",   "reports/q4.pdf",   True),
    ("token-alice",  "acme-corp",  "delete", "reports/q4.pdf",   True),   # admin can delete
    ("token-bob",    "globex",     "read",   "invoices/inv-001", True),
    ("token-bob",    "globex",     "write",  "invoices/inv-001", True),
    ("token-carol",  "initech",    "read",   "wiki/home",        True),
    # Cross-tenant attempt — alice's token used against globex tenant
    ("token-alice",  "globex",     "read",   "reports/secret",   None),   # wrong tenant SDK
]

print(f"\n{'Token':<15} {'Tenant':<12} {'Action':<8} {'Resource':<25} {'Result'}")
print("-"*75)

for token, tenant_id, action, resource, _ in requests:
    sdk = tenants.get(tenant_id)
    if sdk is None:
        print(f"{token:<15} {tenant_id:<12} {action:<8} {resource:<25} ✗ Unknown tenant")
        continue

    decision = sdk.authorize(token, action=action, resource=resource)
    subject   = decision.claims.get("sub", "?")
    claim_tid = decision.claims.get("tenant_id", "?")

    # Tenant isolation: reject if token's tenant_id ≠ requested tenant
    if claim_tid != tenant_id:
        print(f"{token:<15} {tenant_id:<12} {action:<8} {resource:<25} "
              f"✗ TENANT MISMATCH — token is for '{claim_tid}', not '{tenant_id}'")
        continue

    if decision.allowed:
        print(f"{token:<15} {tenant_id:<12} {action:<8} {resource:<25} "
              f"✓ allowed  (sub={subject})")
    else:
        print(f"{token:<15} {tenant_id:<12} {action:<8} {resource:<25} "
              f"✗ denied   ({decision.reason})")

# ── Show call audit per tenant ────────────────────────────────────────────────
print("\nCall audit per tenant:")
for tid, sdk in tenants.items():
    print(f"  {tid}: {len(sdk.authorize_calls)} authorize calls")

print("\n✓ Multi-tenant isolation working correctly")
