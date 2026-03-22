"""
CoreSDK — Example 01: Quickstart
=================================
The minimum code to get started. Connects to the real sidecar,
validates a token, evaluates a policy, checks a rate limit, and more.

Run:
    pip install coresdk
    export CORESDK_SIDECAR_ADDR=localhost:50051
    python 01_quickstart.py
"""

from coresdk import SDK

# ── Connect to sidecar via environment variables ──────────────────────────────
# Reads: CORESDK_SIDECAR_ADDR (default localhost:50051)
#        CORESDK_TENANT_ID    (default "default")
#        CORESDK_FAIL_MODE    (default "open")
sdk = SDK.from_env()

print("CoreSDK Quickstart")
print("=" * 40)

# ── 1. Authorize a token ──────────────────────────────────────────────────────
# No JWKS configured → sidecar returns fail-open (allowed=True)
# Set CORESDK_JWKS_URI=https://your-idp/.well-known/jwks.json for real JWT validation
token = "my-service-token"
decision = sdk.authorize(token, action="read", resource="reports/q4")

print("\n1. authorize()")
print(f"   allowed : {decision.allowed}")
print(f"   reason  : {decision.reason!r}")
print(f"   claims  : {decision.claims}")

# ── 2. Evaluate a policy ──────────────────────────────────────────────────────
# No Rego bundle loaded → sidecar returns fail-open (True)
# Load .rego files via control plane or CORESDK_POLICY_DIR for real evaluation
allowed = sdk.evaluate_policy(
    "data.authz.allow",
    {
        "subject": "alice",
        "action": "read",
        "resource": "reports/q4",
    },
)

print("\n2. evaluate_policy()")
print(f"   data.authz.allow -> {allowed}")

# ── 3. Rate limiting ──────────────────────────────────────────────────────────
rate = sdk.check_rate_limit("user:alice")

print("\n3. check_rate_limit()")
print(f"   allowed   : {rate.allowed}")
print(f"   remaining : {rate.remaining}")

# ── 4. Feature flags ──────────────────────────────────────────────────────────
flag = sdk.evaluate_flag("new_dashboard", user_id="alice")

print("\n4. evaluate_flag()")
print(f"   enabled : {flag.enabled}")
print(f"   variant : {flag.variant!r}")

# ── 5. License entitlement ────────────────────────────────────────────────────
lic = sdk.check_entitlement("sso")

print("\n5. check_entitlement()")
print(f"   entitled : {lic.entitled}")
print(f"   plan     : {lic.plan!r}")

# ── 6. Token revocation ───────────────────────────────────────────────────────
sdk.revoke_token(token, reason="user-logout")
revoked = sdk.is_revoked(token)

print("\n6. revoke_token() / is_revoked()")
print(f"   is_revoked : {revoked}")

print("\n--- SDK connected and working ---")
