"""
CoreSDK — Example 05: Fine-Grained Policy Enforcement
======================================================
Rego-based RBAC + ABAC policy enforcement patterns.

Shows:
  - Role-based access (admin / editor / viewer)
  - Resource ownership check (only owner can edit their own docs)
  - Tenant isolation (tenant A cannot access tenant B resources)
  - Action-level control (read vs write vs delete vs admin)
  - Policy audit trail (log every decision)

Run:
    python 05_policy_enforcement.py
"""
import sys
sys.path.insert(0, "/tmp/coresdk-sdk-python")

from coresdk._types import AuthDecision
from coresdk.testing._mock import MockSDK

RESET = "\033[0m"; GREEN = "\033[32m"; RED = "\033[31m"
CYAN  = "\033[36m"; BOLD  = "\033[1m"; DIM  = "\033[2m"; YEL = "\033[33m"

print(f"\n{BOLD}{CYAN}CoreSDK — Policy Enforcement Patterns{RESET}")
print(f"{CYAN}{'='*50}{RESET}")

# ── Policy engine wrapper ──────────────────────────────────────────────────────
class PolicyEngine:
    """
    Wraps CoreSDK policy calls with business-level logic.
    Production: swap MockSDK for CoreSDKClient(SDKConfig.from_env())
    The Rego bundle on the sidecar implements the actual allow/deny rules.
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


# ── Mock SDK wired with realistic policy rules ─────────────────────────────────
# In production the sidecar evaluates real Rego. Here we simulate via MockSDK
# by overriding evaluate_policy with a simple rule engine.

class RuleBasedMock(MockSDK):
    """MockSDK that applies realistic RBAC + ABAC rules instead of always-True."""

    ROLES: dict[str, list[str]] = {
        "alice":  ["admin", "editor", "viewer"],
        "bob":    ["editor", "viewer"],
        "carol":  ["viewer"],
        "hacker": [],
    }

    ACTION_REQUIRES: dict[str, str] = {
        "read":          "viewer",
        "list":          "viewer",
        "write":         "editor",
        "create":        "editor",
        "update":        "editor",
        "delete":        "admin",
        "admin.promote": "admin",
        "admin.billing": "admin",
    }

    def evaluate_policy(self, rule: str, input_data: dict) -> bool:
        self.policy_calls.append({"rule": rule, "input": input_data})

        subject   = input_data.get("subject", "")
        action    = input_data.get("action", "")
        resource  = input_data.get("resource", "")
        tenant    = input_data.get("tenant_id", "")
        context   = input_data.get("context", {})

        # Rule 1: tenant isolation — resource tenant must match token tenant
        resource_tenant = context.get("resource_tenant", tenant)
        if resource_tenant != tenant:
            return False

        # Rule 2: RBAC — action requires minimum role
        required_role = self.ACTION_REQUIRES.get(action, "admin")
        user_roles    = self.ROLES.get(subject, [])
        role_priority = ["viewer", "editor", "admin"]

        required_idx = role_priority.index(required_role) if required_role in role_priority else 99
        user_max_idx = max((role_priority.index(r) for r in user_roles if r in role_priority),
                           default=-1)

        if user_max_idx < required_idx:
            return False

        # Rule 3: ownership — "update" on a doc only if owner matches
        if action == "update":
            owner = context.get("owner")
            if owner and owner != subject:
                return False

        return True


sdk = RuleBasedMock()
policy = PolicyEngine(sdk)

# ── Test scenarios ─────────────────────────────────────────────────────────────
results = []
def check(label, got, want):
    passed = got == want
    results.append((label, passed))
    mark   = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
    detail = f"expected={want} got={got}"
    print(f"  {mark}  {label:<52}  {DIM}{detail}{RESET}")

print(f"\n{BOLD}RBAC — role-based actions{RESET}")
check("alice  read  report         (admin→ viewer ok)",  policy.can("alice",  "read",   "report",  "acme"), True)
check("alice  delete report        (admin can delete)",  policy.can("alice",  "delete", "report",  "acme"), True)
check("bob    write  doc           (editor can write)",  policy.can("bob",    "write",  "doc",     "acme"), True)
check("bob    delete doc           (editor cannot del)", policy.can("bob",    "delete", "doc",     "acme"), False)
check("carol  read  wiki           (viewer can read)",   policy.can("carol",  "read",   "wiki",    "acme"), True)
check("carol  create doc           (viewer cannot cre)", policy.can("carol",  "create", "doc",     "acme"), False)
check("hacker read  anything       (no roles → deny)",   policy.can("hacker", "read",   "anything","acme"), False)

print(f"\n{BOLD}ABAC — attribute-based (ownership){RESET}")
check("alice updates her own doc   (owner=alice → ok)",
      policy.can("alice", "update", "doc-1", "acme", {"owner": "alice"}), True)
check("bob updates alice's doc     (owner=alice, bob → deny)",
      policy.can("bob",   "update", "doc-1", "acme", {"owner": "alice"}), False)
check("alice updates bob's doc     (owner=bob, alice is admin → still deny by rule)",
      policy.can("alice", "update", "doc-1", "acme", {"owner": "bob"}), False)

print(f"\n{BOLD}Tenant isolation{RESET}")
check("alice reads acme resource   (tenant match → ok)",
      policy.can("alice", "read", "acme/data", "acme",
                 {"resource_tenant": "acme"}), True)
check("alice reads globex resource (tenant mismatch → deny)",
      policy.can("alice", "read", "globex/data", "acme",
                 {"resource_tenant": "globex"}), False)

print(f"\n{BOLD}Admin actions{RESET}")
check("alice admin.billing         (admin role → ok)",
      policy.can("alice", "admin.billing", "settings", "acme"), True)
check("bob   admin.billing         (editor role → deny)",
      policy.can("bob",   "admin.billing", "settings", "acme"), False)
check("alice admin.promote         (admin role → ok)",
      policy.can("alice", "admin.promote", "users/carol", "acme"), True)

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
sys.exit(0 if passed == total else 1)
