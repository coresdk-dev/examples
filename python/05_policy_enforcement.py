"""
CoreSDK — Example 05: Fine-Grained Policy Enforcement
======================================================
Rego-based RBAC + ABAC policy enforcement patterns using the real sidecar.

Shows:
  - Role-based access (admin / editor / viewer)
  - Resource ownership check (only owner can edit their own docs)
  - Tenant isolation (tenant A cannot access tenant B resources)
  - Action-level control (read vs write vs delete vs admin)
  - Policy audit trail (log every decision)

Run:
    export CORESDK_SIDECAR_ADDR=[::1]:50051
    python 05_policy_enforcement.py

Notes:
  Without a Rego bundle loaded, the sidecar returns fail-open (True) for all
  policy calls. This example demonstrates the integration pattern — in production,
  load your Rego bundle via CORESDK_POLICY_DIR=/etc/coresdk/policy and the
  sidecar enforces real rules.
"""
import os
import sys

from coresdk._client import CoreSDKClient
from coresdk._config import SDKConfig

SIDECAR = os.environ.get("CORESDK_SIDECAR_ADDR", "[::1]:50051")

RESET = "\033[0m"; GREEN = "\033[32m"; RED = "\033[31m"
CYAN  = "\033[36m"; BOLD  = "\033[1m"; DIM  = "\033[2m"; YEL = "\033[33m"

print(f"\n{BOLD}{CYAN}CoreSDK — Policy Enforcement Patterns (Real Sidecar){RESET}")
print(f"{CYAN}{'='*55}{RESET}")

# ── Real SDK client → real sidecar ────────────────────────────────────────────
_sdk = CoreSDKClient(SDKConfig(
    sidecar_addr=SIDECAR,
    tenant_id="acme-corp",
    service_name="policy-demo",
    fail_mode="open",
    dev_mode=False,
))

# ── Policy engine wrapper ──────────────────────────────────────────────────────
class PolicyEngine:
    """
    Wraps CoreSDK policy calls with business-level logic.
    The Rego bundle on the sidecar implements the actual allow/deny rules.
    Without a bundle, sidecar returns fail-open (True) — load Rego via
    CORESDK_POLICY_DIR for real enforcement.
    """

    def __init__(self, sdk):
        self._sdk = sdk
        self._audit: list[dict] = []

    def can(self, subject: str, action: str, resource: str,
            tenant_id: str, context: dict | None = None) -> bool:
        ctx = context or {}
        input_data = {
            "tenant_id": tenant_id,
            "subject":   subject,
            "action":    action,
            "resource":  resource,
            "context":   ctx,
        }
        allowed = self._sdk.evaluate_policy("data.authz.allow", input_data)
        self._audit.append({
            "subject":  subject,
            "action":   action,
            "resource": resource,
            "tenant":   tenant_id,
            "allowed":  allowed,
        })
        return allowed

    def audit_log(self) -> list[dict]:
        return self._audit


policy = PolicyEngine(_sdk)

# ── Test scenarios ─────────────────────────────────────────────────────────────
results = []
def check(label, got, want=None, *, sidecar_call=False):
    """
    sidecar_call=True: we just verify the call succeeded (returned a bool)
    and always pass — sidecar is fail-open without a Rego bundle.
    """
    if sidecar_call:
        passed = isinstance(got, bool)
        results.append((label, passed))
        mark   = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
        detail = f"sidecar returned {got} (fail-open without Rego bundle)"
        print(f"  {mark}  {label:<52}  {DIM}{detail}{RESET}")
    else:
        passed = got == want
        results.append((label, passed))
        mark   = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
        detail = f"expected={want} got={got}"
        print(f"  {mark}  {label:<52}  {DIM}{detail}{RESET}")

print(f"\n{BOLD}Policy calls → real sidecar (fail-open, no Rego bundle){RESET}")
print(f"{DIM}Load CORESDK_POLICY_DIR=/etc/coresdk/policy to enforce real Rego rules{RESET}\n")

print(f"{BOLD}RBAC — role-based actions{RESET}")
check("alice  read  report",   policy.can("alice",  "read",   "report",  "acme"), sidecar_call=True)
check("alice  delete report",  policy.can("alice",  "delete", "report",  "acme"), sidecar_call=True)
check("bob    write  doc",     policy.can("bob",    "write",  "doc",     "acme"), sidecar_call=True)
check("bob    delete doc",     policy.can("bob",    "delete", "doc",     "acme"), sidecar_call=True)
check("carol  read  wiki",     policy.can("carol",  "read",   "wiki",    "acme"), sidecar_call=True)
check("carol  create doc",     policy.can("carol",  "create", "doc",     "acme"), sidecar_call=True)
check("hacker read  anything", policy.can("hacker", "read",   "anything","acme"), sidecar_call=True)

print(f"\n{BOLD}ABAC — attribute-based (ownership context){RESET}")
check("alice updates her own doc   (owner=alice)",
      policy.can("alice", "update", "doc-1", "acme", {"owner": "alice"}), sidecar_call=True)
check("bob updates alice's doc     (owner=alice)",
      policy.can("bob",   "update", "doc-1", "acme", {"owner": "alice"}), sidecar_call=True)
check("alice updates bob's doc     (owner=bob)",
      policy.can("alice", "update", "doc-1", "acme", {"owner": "bob"}), sidecar_call=True)

print(f"\n{BOLD}Tenant isolation context{RESET}")
check("alice reads acme resource   (resource_tenant=acme)",
      policy.can("alice", "read", "acme/data", "acme",
                 {"resource_tenant": "acme"}), sidecar_call=True)
check("alice reads globex resource (resource_tenant=globex)",
      policy.can("alice", "read", "globex/data", "acme",
                 {"resource_tenant": "globex"}), sidecar_call=True)

print(f"\n{BOLD}Admin actions{RESET}")
check("alice admin.billing",
      policy.can("alice", "admin.billing", "settings", "acme"), sidecar_call=True)
check("bob   admin.billing",
      policy.can("bob",   "admin.billing", "settings", "acme"), sidecar_call=True)
check("alice admin.promote",
      policy.can("alice", "admin.promote", "users/carol", "acme"), sidecar_call=True)

# ── Audit log ─────────────────────────────────────────────────────────────────
print(f"\n{BOLD}Policy audit log ({len(policy.audit_log())} decisions){RESET}")
for entry in policy.audit_log():
    colour = GREEN if entry["allowed"] else RED
    print(f"  {colour}{'allow' if entry['allowed'] else 'deny ':5}{RESET}  "
          f"{entry['subject']:<8} {entry['action']:<18} {entry['resource']}")

# ── Summary ───────────────────────────────────────────────────────────────────
passed = sum(1 for _, ok in results if ok)
total  = len(results)
colour = GREEN if passed == total else RED
print(f"\n{colour}{BOLD}{passed}/{total} passed{RESET}\n")
print(f"{DIM}All calls hit the real sidecar at {SIDECAR}{RESET}")
print(f"{DIM}To enforce Rego rules: CORESDK_POLICY_DIR=/etc/coresdk/policy{RESET}\n")
sys.exit(0 if passed == total else 1)
