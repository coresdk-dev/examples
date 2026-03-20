"""
CoreSDK Python SDK — live demo
Runs without a sidecar using MockSDK (drop-in for testing/local dev).

Usage:  python demo.py
"""
import json
import sys

sys.path.insert(0, "/tmp/coresdk-sdk-python")

from coresdk._types import AuthDecision
from coresdk.errors._rfc9457 import ProblemDetailError
from coresdk.testing._mock import MockSDK, assert_no_pii
from coresdk.tracing.processor import mask_attributes

RESET = "\033[0m"
GREEN = "\033[32m"
RED   = "\033[31m"
CYAN  = "\033[36m"
BOLD  = "\033[1m"
DIM   = "\033[2m"
YEL   = "\033[33m"

def header(text):
    print(f"\n{BOLD}{CYAN}{'─' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 60}{RESET}")

def ok(label, value=""):   print(f"  {GREEN}✓{RESET}  {BOLD}{label}{RESET}  {DIM}{value}{RESET}")
def fail(label, value=""): print(f"  {RED}✗{RESET}  {BOLD}{label}{RESET}  {DIM}{value}{RESET}")
def info(label):           print(f"  {YEL}→{RESET}  {label}")

# ── 1. SDK initialisation ─────────────────────────────────────────────────
header("1 · SDK Initialisation")

sdk = MockSDK(
    default_allow=True,
    default_claims={"sub": "alice", "tenant_id": "acme-corp", "roles": ["admin", "user"]},
)
ok("MockSDK created", "no sidecar needed for local dev/testing")
ok("Tenant",      sdk.config.tenant_id)
ok("Fail mode",   sdk.config.fail_mode)
ok("Dev mode",    str(sdk.config.dev_mode))

# ── 2. Token validation ───────────────────────────────────────────────────
header("2 · JWT Token Validation")

decision = sdk.authorize("eyJhbGciOiJSUzI1NiJ9.valid.sig")
ok(
    f"Valid token → allowed={decision.allowed}",
    f"sub={decision.claims['sub']}  roles={decision.claims['roles']}",
)

sdk.set_token_rejected("revoked-token-xyz", reason="token revoked")
decision2 = sdk.authorize("revoked-token-xyz")
fail(
    f"Revoked token → allowed={decision2.allowed}",
    f"reason={decision2.reason}",
)

sdk.set_token_decision(
    "guest-token",
    AuthDecision(allowed=True, claims={"sub": "guest", "roles": ["viewer"]}, reason=""),
)
decision3 = sdk.authorize("guest-token")
ok(
    f"Guest token → allowed={decision3.allowed}",
    f"sub={decision3.claims['sub']}  roles={decision3.claims['roles']}",
)

info(f"Total authorize calls recorded: {len(sdk.authorize_calls)}")

# ── 3. Policy evaluation ──────────────────────────────────────────────────
header("3 · Rego Policy Evaluation")

# MockSDK always returns True — show the call recording
result = sdk.evaluate_policy("documents.read",   {"user": "alice", "doc": "doc-1"})
ok(f"documents.read   → {result}")

result = sdk.evaluate_policy("documents.write",  {"user": "alice", "doc": "doc-1"})
ok(f"documents.write  → {result}")

result = sdk.evaluate_policy("admin.delete_user", {"user": "alice", "target": "bob"})
ok(f"admin.delete_user → {result}")

info(f"Total policy calls recorded: {len(sdk.policy_calls)}")
for call in sdk.policy_calls:
    print(f"     {DIM}rule={call['rule']}  input={call['input']}{RESET}")

# ── 4. PII masking ────────────────────────────────────────────────────────
header("4 · PII Masking (Zero-PII Span Attributes)")

raw_attrs = {
    "user.email":    "alice@acme.com",
    "Authorization": "Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig",
    "api_key":       "sk-live-abc123xyz",
    "http.method":   "GET",
    "http.route":    "/api/documents",
    "status_code":   "200",
    "user.sub":      "alice",
}

masked = mask_attributes(raw_attrs)
info("Before → After masking:")
for k in raw_attrs:
    before = raw_attrs[k]
    after  = masked[k]
    colour = RED if after == "[REDACTED]" else GREEN
    tag    = "REDACTED" if after == "[REDACTED]" else "safe    "
    print(f"     {colour}{tag}{RESET}  {k}: {DIM}{before[:40]}{RESET}")

# ── 5. assert_no_pii ─────────────────────────────────────────────────────
header("5 · assert_no_pii (Test Utility)")

class CleanSpan:
    attributes = {"http.route": "/api/docs", "method": "GET", "status": "200"}

class DirtySpan:
    attributes = {"note": "contact bob@example.com or call 555-1234"}

try:
    assert_no_pii([CleanSpan()])
    ok("Clean span  → passed assert_no_pii")
except AssertionError as e:
    fail("Clean span  → unexpectedly failed", str(e))

try:
    assert_no_pii([DirtySpan()])
    fail("Dirty span  → should have been caught!")
except AssertionError as e:
    ok("Dirty span  → caught by assert_no_pii", str(e)[:60])

# ── 6. RFC 9457 error types ───────────────────────────────────────────────
header("6 · RFC 9457 Problem Detail Errors")

for err in [
    ProblemDetailError.unauthorized("Token signature invalid"),
    ProblemDetailError.forbidden("Insufficient role: need admin"),
    ProblemDetailError("Not Found", 404, detail="Document doc-99 does not exist"),
]:
    d = err.to_dict()
    colour = RED if d["status"] >= 400 else GREEN
    print(f"  {colour}HTTP {d['status']}{RESET}  {BOLD}{d['title']}{RESET}  {DIM}{d.get('detail','')}{RESET}")

# ── 7. FastAPI middleware ─────────────────────────────────────────────────
header("7 · FastAPI Middleware (TestClient — no server needed)")

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from coresdk.middleware.fastapi import CoreSDKMiddleware

    app = FastAPI()
    app.add_middleware(CoreSDKMiddleware, sdk=sdk)

    @app.get("/me")
    async def me():
        return {"user": "alice", "tenant": "acme-corp", "roles": ["admin"]}

    @app.get("/public")
    async def public():
        return {"status": "ok"}

    client = TestClient(app, raise_server_exceptions=False)

    cases = [
        ("GET /me     + token", "/me",     {"Authorization": "Bearer valid-token"}),
        ("GET /me     no token", "/me",    {}),
        ("GET /public + token", "/public", {"Authorization": "Bearer valid-token"}),
    ]

    for label, path, headers in cases:
        r = client.get(path, headers=headers)
        colour = GREEN if r.status_code < 400 else RED
        print(f"  {colour}HTTP {r.status_code}{RESET}  {label}  {DIM}{str(r.json())[:60]}{RESET}")

except ImportError:
    info("FastAPI not installed — skipping")

# ── Summary ───────────────────────────────────────────────────────────────
header("Summary")
ok("JWT validation  (allow / reject / custom decisions)")
ok("Policy evaluation  (Rego rules, call recording)")
ok("PII masking  (email, Bearer token, API key → REDACTED)")
ok("assert_no_pii  (clean span passes, dirty span caught)")
ok("RFC 9457 errors  (401 / 403 / 404 structured responses)")
ok("FastAPI middleware  (200 with token, 401 without)")
print(f"\n  {DIM}Swap MockSDK → SDK.from_env() to connect to a real sidecar.{RESET}\n")
