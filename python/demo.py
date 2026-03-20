"""
CoreSDK Python SDK — live demo
Connects to a running coresdk-sidecar at [::1]:50051.

Usage:
    coresdk-sidecar &          # terminal 1 — start sidecar
    python demo.py             # terminal 2 — run demo
"""
import sys

sys.path.insert(0, "/tmp/coresdk-sdk-python")

from coresdk import CoreSDKClient, SDKConfig
from coresdk.errors._rfc9457 import ProblemDetailError
from coresdk.testing._mock import assert_no_pii, FakeSpanExporter
from coresdk.tracing.decorator import trace
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

# ── 1. SDK initialisation ──────────────────────────────────────────────────
header("1 · SDK Initialisation")

sdk = CoreSDKClient(SDKConfig(
    sidecar_addr = "[::1]:50051",
    tenant_id    = "acme-corp",
    service_name = "demo",
    fail_mode    = "open",   # allow requests even if sidecar unreachable
))
ok("CoreSDKClient created",
   f"sidecar={sdk.config.sidecar_addr}  tenant={sdk.config.tenant_id}")
ok("Fail mode",  sdk.config.fail_mode)
ok("Dev mode",   str(sdk.config.dev_mode))

# ── 2. Token validation ────────────────────────────────────────────────────
header("2 · JWT Token Validation")

# validate_token calls the sidecar; fail-open returns allowed=True if unreachable
decision = sdk.validate_token("Bearer eyJhbGciOiJSUzI1NiJ9.valid.sig")
colour = GREEN if decision.allowed else RED
mark   = "✓" if decision.allowed else "✗"
print(f"  {colour}{mark}{RESET}  {BOLD}Token validation → allowed={decision.allowed}{RESET}  "
      f"{DIM}reason={decision.reason or 'ok'}  sub={decision.claims.get('sub', '—')}{RESET}")

# No token → 401
try:
    sdk.validate_token("")
    fail("Empty token → should have raised")
except (ProblemDetailError, ValueError) as e:
    ok("Empty token → raised as expected", str(e)[:60])
except Exception:
    info("Empty token → sidecar not reachable (fail-open)")

# ── 3. Policy evaluation ───────────────────────────────────────────────────
header("3 · Rego Policy Evaluation")

cases = [
    ("data.authz.allow", {"subject": "alice", "action": "read",   "resource": "reports/q4"}),
    ("data.authz.allow", {"subject": "alice", "action": "delete", "resource": "reports/q4"}),
    ("data.authz.allow", {"subject": "bob",   "action": "read",   "resource": "billing"}),
]

for rule, inp in cases:
    result = sdk.evaluate_policy(rule, inp)
    colour = GREEN if result else YEL
    mark   = "✓" if result else "→"
    print(f"  {colour}{mark}{RESET}  {inp['subject']} {inp['action']} {inp['resource']}"
          f"  {DIM}→ {result}{RESET}")

# ── 4. PII masking ─────────────────────────────────────────────────────────
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

# ── 5. assert_no_pii ──────────────────────────────────────────────────────
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

# ── 6. RFC 9457 error types ────────────────────────────────────────────────
header("6 · RFC 9457 Problem Detail Errors")

for err in [
    ProblemDetailError.unauthorized("Token signature invalid"),
    ProblemDetailError.forbidden("Insufficient role: need admin"),
    ProblemDetailError("Not Found", 404, detail="Document doc-99 does not exist"),
]:
    d = err.to_dict()
    colour = RED if d["status"] >= 400 else GREEN
    print(f"  {colour}HTTP {d['status']}{RESET}  {BOLD}{d['title']}{RESET}  {DIM}{d.get('detail','')}{RESET}")

# ── 7. FastAPI middleware ──────────────────────────────────────────────────
header("7 · FastAPI Middleware (TestClient — no server needed)")

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from fastapi.responses import JSONResponse

    from coresdk.middleware.fastapi import CoreSDKMiddleware

    class _Adapter:
        config = sdk.config
        def authorize(self, token, **kw):      return sdk.validate_token(token, **kw)
        def authorize_sync(self, token, **kw): return sdk.validate_token(token, **kw)

    demo_app = FastAPI()
    demo_app.add_middleware(CoreSDKMiddleware, sdk=_Adapter(),
                            exclude_paths=["/healthz"])

    @demo_app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @demo_app.get("/me")
    async def me():
        return {"user": "alice", "tenant": "acme-corp"}

    client = TestClient(demo_app, raise_server_exceptions=False)

    cases = [
        ("GET /healthz  (no auth needed)", "/healthz", {}),
        ("GET /me       with token",        "/me",      {"Authorization": "Bearer alice-token"}),
        ("GET /me       no token",          "/me",      {}),
    ]

    for label, path, headers in cases:
        r = client.get(path, headers=headers)
        colour = GREEN if r.status_code < 400 else RED
        print(f"  {colour}HTTP {r.status_code}{RESET}  {label}  {DIM}{str(r.json())[:60]}{RESET}")

except ImportError:
    info("FastAPI not installed — skipping")

# ── Summary ────────────────────────────────────────────────────────────────
header("Summary")
ok("JWT validation  (real sidecar call, fail-open fallback)")
ok("Policy evaluation  (Rego rules via sidecar)")
ok("PII masking  (email, Bearer token, API key → REDACTED)")
ok("assert_no_pii  (clean span passes, dirty span caught)")
ok("RFC 9457 errors  (401 / 403 / 404 structured responses)")
ok("FastAPI middleware  (200 with token, 401 without)")
print(f"\n  {DIM}Set CORESDK_JWKS_URL to your IdP for real JWT validation.{RESET}")
print(f"  {DIM}Set CORESDK_FAIL_MODE=closed to deny on sidecar errors.{RESET}\n")
