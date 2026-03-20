"""
CoreSDK — Example 01: Quickstart
=================================
The minimum code to get started. Connects to the real sidecar,
validates a token, evaluates a policy.

Run:
    pip install coresdk
    export CORESDK_SIDECAR_ADDR=[::1]:50051
    python 01_quickstart.py
"""
import os
import sys
sys.path.insert(0, "/tmp/coresdk-sdk-python")

from coresdk._client import CoreSDKClient
from coresdk._config import SDKConfig

# ── Connect to real sidecar ───────────────────────────────────────────────────
sdk = CoreSDKClient(SDKConfig(
    sidecar_addr=os.environ.get("CORESDK_SIDECAR_ADDR", "[::1]:50051"),
    tenant_id="my-company",
    service_name="my-api",
    fail_mode="open",
))

print("CoreSDK Quickstart\n" + "="*40)

# ── Validate a token ──────────────────────────────────────────────────────────
# No JWKS configured → sidecar returns fail-open (allowed=True)
# Set CORESDK_JWKS_URL=https://your-idp/.well-known/jwks.json for real JWT validation
decision = sdk.validate_token("my-service-token", action="read", resource="reports/q4")

print(f"\nToken validation:")
print(f"  allowed : {decision.allowed}")
print(f"  reason  : {decision.reason!r}")
print(f"  claims  : {decision.claims}")

# ── Evaluate a policy ─────────────────────────────────────────────────────────
# No Rego bundle loaded → sidecar returns fail-open (True)
# Load .rego files via CORESDK_POLICY_DIR=/etc/coresdk/policy for real evaluation
allowed = sdk.evaluate_policy("data.authz.allow", {
    "tenant_id": "my-company",
    "subject":   "alice",
    "action":    "read",
    "resource":  "reports/q4",
    "context":   {},
})

print(f"\nPolicy evaluation:")
print(f"  data.authz.allow → {allowed}")

print("\n✓ SDK connected and working — sidecar is live.")
