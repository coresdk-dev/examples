"""
CoreSDK — Example 06: PII-Safe Tracing
=======================================
How to instrument your service with OpenTelemetry spans and guarantee
no PII ever reaches your observability backend.

CoreSDK's SpanProcessor masks sensitive attributes before export —
emails, tokens, API keys, SSNs, credit card numbers, JWTs.

Also demonstrates local PII masking via coresdk.masking — no sidecar needed.

Run:
    python 06_pii_safe_tracing.py
"""
import sys

from coresdk.masking import MaskingConfig, mask_dict, mask_string
from coresdk.tracing.decorator import trace
from coresdk.tracing.processor import REDACTED, mask_attributes, mask_value
from coresdk.testing._mock import assert_no_pii

RESET = "\033[0m"; GREEN = "\033[32m"; RED = "\033[31m"
CYAN  = "\033[36m"; BOLD  = "\033[1m"; DIM  = "\033[2m"

results = []
def check(label, passed, detail=""):
    results.append((label, passed))
    mark = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
    print(f"  {mark}  {label:<55}  {DIM}{detail}{RESET}")

print(f"\n{BOLD}{CYAN}CoreSDK — PII-Safe Tracing{RESET}")
print(f"{CYAN}{'='*50}{RESET}")

# ── 1. mask_value — single value redaction ────────────────────────────────────
print(f"\n{BOLD}1. Single value masking{RESET}")

cases = [
    ("email",       "alice@acme.com",                         True),
    ("JWT",         "eyJhbGciOiJSUzI1NiJ9.payload.sig",       True),
    ("Bearer",      "Bearer eyJhbGciOiJSUzI1NiJ9.p.s",        True),
    ("API key",     "sk-live-xK9mNpQrStUv",                   True),
    ("SSN",         "123-45-6789",                             True),
    ("safe route",  "/api/documents",                          False),
    ("safe status", "200",                                     False),
    ("safe action", "GET",                                     False),
]

for label, value, should_redact in cases:
    result   = mask_value(value)
    redacted = result == REDACTED
    ok       = redacted == should_redact
    detail   = f"[REDACTED]" if redacted else f'"{result}"'
    check(f"{label:<14} → {'REDACTED' if should_redact else 'preserved'}", ok, detail)

# ── 2. mask_attributes — span attribute dict ──────────────────────────────────
print(f"\n{BOLD}2. Span attribute masking (dict){RESET}")

raw_span_attrs = {
    # PII — must be redacted
    "user.email":        "alice@example.com",
    "http.request.header.authorization": "Bearer eyJhbGciOiJSUzI1NiJ9.abc.def",
    "api_key":           "sk-live-abc123",
    "user.ssn":          "555-12-3456",
    # Safe — must be preserved
    "http.method":       "POST",
    "http.route":        "/api/orders",
    "http.status_code":  "201",
    "service.name":      "order-service",
    "tenant_id":         "acme-corp",
}

masked = mask_attributes(raw_span_attrs)

pii_fields  = ["user.email", "http.request.header.authorization", "api_key", "user.ssn"]
safe_fields = ["http.method", "http.route", "http.status_code", "service.name", "tenant_id"]

for f in pii_fields:
    check(f"PII  '{f}' → [REDACTED]", masked[f] == REDACTED, masked[f])

for f in safe_fields:
    check(f"Safe '{f}' → preserved", masked[f] == raw_span_attrs[f], masked[f])

# ── 3. assert_no_pii — use in your test suite ────────────────────────────────
print(f"\n{BOLD}3. assert_no_pii in tests{RESET}")

class GoodSpan:
    """Span with only safe attributes."""
    attributes = {
        "http.method": "GET",
        "http.route": "/api/products",
        "tenant_id": "acme-corp",
        "duration_ms": "42",
    }

class BadSpan:
    """Span that accidentally contains PII."""
    attributes = {
        "http.method": "POST",
        "http.route": "/api/users",
        "user.data": "name=Alice email=alice@acme.com",  # leaked PII!
    }

# Good span must pass
try:
    assert_no_pii([GoodSpan()])
    check("assert_no_pii passes on clean span", True)
except AssertionError as e:
    check("assert_no_pii passes on clean span", False, str(e))

# Bad span must be caught
try:
    assert_no_pii([BadSpan()])
    check("assert_no_pii catches PII in span", False, "should have raised!")
except AssertionError as e:
    check("assert_no_pii catches PII in span", True, str(e)[:60])

# ── 4. @trace decorator ───────────────────────────────────────────────────────
print(f"\n{BOLD}4. @trace decorator{RESET}")

@trace(intent="process-order")
async def process_order(order_id: str, tenant: str) -> dict:
    """Business logic — CoreSDK creates a span with coresdk.intent automatically."""
    return {"order_id": order_id, "tenant": tenant, "status": "processed"}

@trace(intent="fetch-user-profile", span_name="UserService.getProfile")
def get_user_profile(user_id: str) -> dict:
    return {"user_id": user_id, "name": "Alice"}

import asyncio
result = asyncio.run(process_order("ord-001", "acme-corp"))
check("@trace async works",  result["status"] == "processed", str(result))

result2 = get_user_profile("usr-123")
check("@trace sync works",   result2["user_id"] == "usr-123", str(result2))

# ── 5. What NOT to put in spans ───────────────────────────────────────────────
print(f"\n{BOLD}5. Safe span attribute patterns{RESET}")

safe_patterns = {
    # ✓ use these
    "user.id":          "usr-abc123",           # opaque ID, not email/name
    "tenant.id":        "acme-corp",
    "order.id":         "ord-789",
    "http.method":      "GET",
    "http.status_code": "200",
    "error.type":       "ValidationError",      # type, not message with user data
}

unsafe_patterns = {
    # ✗ never put these in spans
    "user.email":       "alice@acme.com",
    "user.password":    "hunter2",
    "credit_card":      "4111 1111 1111 1111",
    "auth_token":       "Bearer eyJ...",
    "user.ssn":         "123-45-6789",
}

safe_masked   = mask_attributes(safe_patterns)
unsafe_masked = mask_attributes(unsafe_patterns)

all_safe_ok   = all(safe_masked[k] == v for k, v in safe_patterns.items())
all_unsafe_ok = all(unsafe_masked[k] == REDACTED for k in unsafe_patterns)

check("Safe ID patterns pass through unmasked",     all_safe_ok)
check("Sensitive patterns all redacted before export", all_unsafe_ok)

# ── 6. Local masking — no sidecar needed ─────────────────────────────────────
print(f"\n{BOLD}6. Local masking (coresdk.masking){RESET}")

# mask_dict: recursively redacts PII in a dict — use before logging or storing
user_profile = {
    "name": "Alice Smith",
    "email": "alice@company.com",
    "ssn": "123-45-6789",
    "credit_card": "4111-1111-1111-1111",
    "notes": "Normal customer",
}
safe_profile = mask_dict(user_profile)

check("mask_dict: name preserved",          safe_profile["name"] == "Alice Smith", safe_profile["name"])
check("mask_dict: email redacted",          safe_profile["email"] == REDACTED,     safe_profile["email"])
check("mask_dict: ssn redacted",            safe_profile["ssn"] == REDACTED,       safe_profile["ssn"])
check("mask_dict: credit_card redacted",    safe_profile["credit_card"] == REDACTED, safe_profile["credit_card"])
check("mask_dict: notes (safe) preserved",  safe_profile["notes"] == "Normal customer", safe_profile["notes"])

# mask_string: inline substitution — PII replaced in-place, context kept
raw_log = "User alice@company.com called from SSN 123-45-6789"
safe_log = mask_string(raw_log)
check("mask_string: email replaced in text", "alice@company.com" not in safe_log, safe_log[:60])
check("mask_string: SSN replaced in text",   "123-45-6789" not in safe_log,       safe_log[:60])
check("mask_string: surrounding text kept",  "User" in safe_log and "called" in safe_log, safe_log[:60])

# Custom patterns via MaskingConfig
config = MaskingConfig(extra_patterns=[r"CUST-\d{6}"])
safe_custom = mask_string("Customer CUST-123456 called", config=config)
check("mask_string: custom pattern redacted",  "CUST-123456" not in safe_custom, safe_custom)
check("mask_string: custom pattern: context kept", "Customer" in safe_custom, safe_custom)

# Allowlist mode — only explicitly safe fields pass through
al_config  = MaskingConfig(allowlist_mode=True, allowlist={"tenant_id", "order_id"})
mixed_data = {"tenant_id": "acme-corp", "order_id": "ord-99", "email": "x@y.com", "ssn": "000-00-0000"}
safe_al    = mask_dict(mixed_data, config=al_config)
check("mask_dict allowlist: tenant_id kept",   safe_al["tenant_id"] == "acme-corp", safe_al["tenant_id"])
check("mask_dict allowlist: order_id kept",    safe_al["order_id"] == "ord-99",     safe_al["order_id"])
check("mask_dict allowlist: email redacted",   safe_al["email"] == REDACTED,        safe_al["email"])
check("mask_dict allowlist: ssn redacted",     safe_al["ssn"] == REDACTED,          safe_al["ssn"])

# ── Summary ───────────────────────────────────────────────────────────────────
passed = sum(1 for _, ok in results if ok)
total  = len(results)
colour = GREEN if passed == total else RED
print(f"\n{colour}{BOLD}{passed}/{total} passed{RESET}\n")
sys.exit(0 if passed == total else 1)
