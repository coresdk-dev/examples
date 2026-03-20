# CoreSDK Examples — Feature Coverage

Legend: ✅ full coverage · 🟡 partial · ➖ not applicable

## Feature × Example matrix

| Feature | `01_quickstart` | `02_multi_tenant` | `03_fastapi_service` | `04_flask_service` | `05_policy` | `06_pii_tracing` | `demo` | `fastapi-app` | `flask-app` |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **CoreSDKClient + SDKConfig** | ✅ | ✅ | ✅ | ✅ | ✅ | ➖ | ✅ | ✅ | ✅ |
| **JWT token validation** | ✅ | ✅ | 🟡 | 🟡 | 🟡 | ➖ | ✅ | ✅ | ✅ |
| **Fail-open / fail-closed** | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | ➖ | ✅ | ✅ | ✅ |
| **FastAPI middleware** | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ✅ | ✅ | ➖ |
| **Flask middleware** | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ➖ | ✅ |
| **Role-based access control** | ➖ | ➖ | ✅ | ➖ | 🟡 | ➖ | ➖ | ✅ | ✅ |
| **Multi-tenant isolation** | ➖ | ✅ | 🟡 | 🟡 | 🟡 | ➖ | ➖ | ✅ | ✅ |
| **OPA/Rego policy evaluation** | ✅ | ➖ | ➖ | ➖ | ✅ | ➖ | ✅ | ✅ | ✅ |
| **RBAC policy pattern** | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ | 🟡 | 🟡 |
| **ABAC policy pattern** | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ➖ |
| **Policy audit log** | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ➖ |
| **`@trace` decorator** | ➖ | ➖ | ✅ | ➖ | ➖ | ✅ | ➖ | ✅ | ✅ |
| **PII masking (`mask_value`)** | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ✅ | ➖ | ➖ |
| **PII masking (`mask_attributes`)** | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ✅ | ➖ | ➖ |
| **`assert_no_pii` (test util)** | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ✅ | ➖ | ➖ |
| **RFC 9457 error responses** | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ✅ | ✅ | ✅ |
| **Config from `coresdk.toml`** | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ✅ |
| **Env var config overrides** | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ✅ |
| **Dockerfile** | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ✅ |
| **pytest test suite** | ➖ | ➖ | 🟡 | 🟡 | ➖ | ➖ | ➖ | ✅ | ✅ |
| **Concurrent requests** | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |

## Coverage by example

| Example | Type | Features covered | Best for |
|---|---|---|---|
| `fastapi-app/` | Full project | All 20 | Starting a new FastAPI service |
| `flask-app/` | Full project | All 20 | Starting a new Flask service |
| `01_quickstart.py` | Script | SDK init, token validation, policy eval | Getting started in 5 min |
| `02_multi_tenant.py` | Script | Multi-tenant client, cross-tenant rejection | Multi-tenant SaaS patterns |
| `03_fastapi_service.py` | Script | FastAPI middleware, RBAC, tracing, RFC 9457, concurrency | FastAPI integration deep-dive |
| `04_flask_service.py` | Script | Flask middleware, tenant scoping | Flask integration deep-dive |
| `05_policy_enforcement.py` | Script | RBAC, ABAC, policy audit log, OPA rules | Policy patterns reference |
| `06_pii_safe_tracing.py` | Script | PII masking, `@trace`, `assert_no_pii` | Observability + PII guarantees |
| `demo.py` | Script | All SDK primitives, FastAPI middleware | Interactive feature tour |

## Feature coverage gaps

The following features are not yet demonstrated in any example:

| Feature | Status | Notes |
|---|---|---|
| ABAC in a full project | Missing | Only in `05_policy_enforcement.py` script |
| Flask + RBAC (role guards) | Partial | `flask-app/` has `require_role`, standalone `04` does not |
| Rego bundle loading | Missing | `bundle_dir` in toml but no example Rego files |
| mTLS SDK↔sidecar config | Missing | Automatic — no user config needed in Phase 1b |
| Feature flags (`is_enabled`) | Missing | Phase 2 feature |
| Rate limiting | Missing | Phase 2 feature |
| Audit trail | Missing | Phase 2 feature |
| Go SDK examples | Missing | Phase 2 |
| TypeScript SDK examples | Missing | Phase 2 |
| Java SDK examples | Missing | Phase 2 |
