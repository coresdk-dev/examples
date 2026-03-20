"""
CoreSDK — Example 01: Quickstart
=================================
The minimum code to get started. Connect the SDK to a running sidecar,
validate a token, evaluate a policy.

Run:
    pip install coresdk
    export CORESDK_SIDECAR_ADDR=[::1]:50051
    python 01_quickstart.py
"""
import sys
sys.path.insert(0, "/tmp/coresdk-sdk-python")

from coresdk._client import CoreSDKClient
from coresdk._config import SDKConfig

# ── 1. Connect ────────────────────────────────────────────────────────────────
sdk = CoreSDKClient(SDKConfig(
    sidecar_addr="[::1]:50051",
    tenant_id="my-company",
    service_name="my-api",
))

# ── 2. Validate a token ───────────────────────────────────────────────────────
decision = sdk.validate_token("Bearer <your-jwt-here>")

if decision.allowed:
    print(f"✓ Authenticated: sub={decision.claims.get('sub')}")
else:
    print(f"✗ Rejected: {decision.reason}")
    sys.exit(1)

# ── 3. Evaluate a policy ──────────────────────────────────────────────────────
allowed = sdk.evaluate_policy("data.authz.allow", {
    "tenant_id": "my-company",
    "subject":   decision.claims.get("sub"),
    "action":    "read",
    "resource":  "documents/report-q4.pdf",
    "context":   {},
})

if allowed:
    print("✓ Authorized: access granted")
else:
    print("✗ Forbidden: policy denied the request")
    sys.exit(1)

print("\nDone — SDK is connected and working.")
