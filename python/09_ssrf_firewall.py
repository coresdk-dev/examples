"""Example: SSRF firewall — block outbound requests to internal IPs."""
from coresdk import SDK
from coresdk.egress import CoreSDKSession

sdk = SDK.from_env()

print("=== SSRF Firewall Example ===\n")

# Direct API check
print("Direct egress check:")
for url in ["https://api.example.com/data", "http://169.254.169.254/latest/meta-data/", "http://192.168.1.1/admin"]:
    decision = sdk.check_egress(url)
    status = "ALLOWED" if decision.allowed else "BLOCKED"
    print(f"  {status}  {url}")
    if not decision.allowed:
        print(f"           reason: {decision.reason}")

print()

# Use CoreSDKSession for automatic SSRF checking
print("Using CoreSDKSession (auto-checks before every request):")
session = CoreSDKSession(sdk)

try:
    # This will be blocked before the request is even sent
    session.get("http://10.0.0.1/internal")
except PermissionError as e:
    print(f"  Blocked: {e}")

print("\nAdd egress_allowlist.rego to restrict to specific domains.")
print("See examples/policy/egress_allowlist.rego")
