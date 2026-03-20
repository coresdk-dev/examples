"""
CoreSDK Python SDK — End-to-End Test
Talks to a REAL running sidecar over gRPC via the SDK client (no mocks).

Usage:  python e2e_test.py
"""
import json, os, sys, time
sys.path.insert(0, "/tmp/coresdk-sdk-python")

import grpc
from coresdk._client import CoreSDKClient
from coresdk._config import SDKConfig
from coresdk.errors._rfc9457 import ProblemDetailError
from coresdk.tracing.processor import mask_attributes

RESET="\033[0m"; GREEN="\033[32m"; RED="\033[31m"; CYAN="\033[36m"
BOLD="\033[1m"; DIM="\033[2m"; YEL="\033[33m"
results = []

def header(t):
    print(f"\n{BOLD}{CYAN}{'─'*62}{RESET}\n{BOLD}{CYAN}  {t}{RESET}\n{BOLD}{CYAN}{'─'*62}{RESET}")

def check(name, passed, detail=""):
    results.append((name, passed))
    tag = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  [{tag}]  {BOLD}{name}{RESET}  {DIM}{detail}{RESET}")

ADDR = os.environ.get("CORESDK_SIDECAR_ADDR", "[::1]:50051")

# ── SDK client (real gRPC, no mock) ──────────────────────────────────────────
config = SDKConfig(sidecar_addr=ADDR, tenant_id="acme", fail_mode="open", dev_mode=False)
client = CoreSDKClient(config)

# ── 1. Health check ───────────────────────────────────────────────────────────
header("1 · Sidecar Health (HTTP)")
import urllib.request

for path, expect_key, expect_val in [
    ("/healthz", "status", "ok"),
    ("/readyz",  "status", "ready"),
]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:9091{path}", timeout=3) as r:
            body = json.loads(r.read())
            check(f"GET {path}", body.get(expect_key) in ("ok","ready"), json.dumps(body))
    except Exception as e:
        check(f"GET {path}", False, str(e))

# ── 2. ValidateToken — allowed (fail-open, no JWKS) ──────────────────────────
header("2 · ValidateToken via SDK Client")

d = client.validate_token("eyJhbGciOiJSUzI1NiJ9.test.payload")
check("Any token → AuthDecision returned",  isinstance(d.allowed, bool),
      f"allowed={d.allowed}  reason={d.reason!r}")
check("Fail-open → allowed=True (no JWKS configured)", d.allowed == True,
      f"allowed={d.allowed}")

# Empty token
d2 = client.validate_token("")
check("Empty token → still returns AuthDecision", isinstance(d2.allowed, bool),
      f"allowed={d2.allowed}  reason={d2.reason!r}")

# ── 3. ValidateToken with action + resource ───────────────────────────────────
header("3 · ValidateToken with action + resource")

d3 = client.validate_token("my-token", action="read", resource="documents/doc-1")
check("token + action + resource → allowed", d3.allowed,
      f"allowed={d3.allowed}  reason={d3.reason!r}")

d4 = client.validate_token("my-token", action="delete", resource="admin/settings")
check("token + action=delete + resource=admin → allowed (fail-open)", d4.allowed,
      f"allowed={d4.allowed}")

# ── 4. EvaluatePolicy ─────────────────────────────────────────────────────────
header("4 · EvaluatePolicy via SDK Client")

cases = [
    ("data.authz.allow", {"tenant_id":"acme","subject":"alice","action":"read","resource":"doc-1","context":{}}),
    ("data.authz.allow", {"tenant_id":"acme","subject":"bob",  "action":"write","resource":"doc-2","context":{}}),
    ("data.authz.allow", {"tenant_id":"acme","subject":"eve",  "action":"delete","resource":"admin","context":{}}),
]

for rule, inp in cases:
    result = client.evaluate_policy(rule, inp)
    check(f"Evaluate {rule} [{inp['subject']} / {inp['action']}]",
          isinstance(result, bool), f"result={result}")

# ── 5. PII masking (local, no sidecar needed) ─────────────────────────────────
header("5 · PII Masking — Zero-PII guarantee")

raw = {
    "user.email":    "alice@acme.com",
    "Authorization": "Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig",
    "api_key":       "sk-live-abc123xyz",
    "http.method":   "GET",
    "http.route":    "/api/docs",
    "status":        "200",
}
masked = mask_attributes(raw)

pii_fields    = ["user.email", "Authorization", "api_key"]
safe_fields   = ["http.method", "http.route", "status"]
pii_redacted  = all(masked[f] == "[REDACTED]" for f in pii_fields)
safe_preserved= all(masked[f] == raw[f] for f in safe_fields)

check("PII fields redacted (email, Bearer, api_key)", pii_redacted,
      str({k: masked[k] for k in pii_fields}))
check("Safe fields preserved (method, route, status)", safe_preserved,
      str({k: masked[k] for k in safe_fields}))

# ── 6. RFC 9457 errors ────────────────────────────────────────────────────────
header("6 · RFC 9457 Problem Detail Errors")

err401 = ProblemDetailError.unauthorized("bad token")
err403 = ProblemDetailError.forbidden("insufficient role")
err404 = ProblemDetailError("Not Found", 404, detail="doc-99 missing")

check("401 Unauthorized — correct status", err401.to_dict()["status"] == 401,
      err401.to_dict()["title"])
check("403 Forbidden    — correct status", err403.to_dict()["status"] == 403,
      err403.to_dict()["title"])
check("404 Not Found    — detail present",  "doc-99" in err404.to_dict().get("detail",""),
      err404.to_dict()["detail"])

# ── 7. Concurrent calls ───────────────────────────────────────────────────────
header("7 · Concurrent calls (20 parallel)")

import concurrent.futures

def call_n(i):
    try:
        d = client.validate_token(f"token-{i}", action="read", resource=f"doc-{i}")
        return d.allowed is not None
    except Exception:
        return False

with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
    futs = [ex.submit(call_n, i) for i in range(20)]
    ok_count = sum(f.result() for f in concurrent.futures.as_completed(futs))

check("20 concurrent ValidateToken calls", ok_count == 20, f"{ok_count}/20 succeeded")

# ── 8. FastAPI end-to-end ─────────────────────────────────────────────────────
header("8 · FastAPI Middleware → real SDK client")

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from coresdk.middleware.fastapi import CoreSDKMiddleware

    # Wrap the real client in a thin shim that matches the middleware's SDK interface
    class RealSDKAdapter:
        config = config

        def authorize(self, token, **kw):
            return client.validate_token(token, **kw)

        def authorize_sync(self, token, **kw):
            return self.authorize(token, **kw)

    app = FastAPI()
    app.add_middleware(CoreSDKMiddleware, sdk=RealSDKAdapter())

    @app.get("/me")
    async def me(): return {"user": "alice", "tenant": "acme"}

    tc = TestClient(app, raise_server_exceptions=False)

    r1 = tc.get("/me", headers={"Authorization": "Bearer real-token"})
    check("FastAPI + real SDK → 200 with token", r1.status_code == 200, str(r1.json()))

    r2 = tc.get("/me")
    check("FastAPI + real SDK → 401 without token", r2.status_code == 401, str(r2.json()))

except ImportError as e:
    check("FastAPI middleware", False, f"import error: {e}")

# ── Summary ───────────────────────────────────────────────────────────────────
header("Summary")
passed = sum(1 for _, ok in results if ok)
total  = len(results)
colour = GREEN if passed == total else RED
for name, ok in results:
    sym = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
    print(f"  {sym}  {name}")
print(f"\n  {colour}{BOLD}{passed}/{total} passed{RESET}\n")
sys.exit(0 if passed == total else 1)
