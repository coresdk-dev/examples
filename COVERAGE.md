# CoreSDK Examples — Feature Coverage

Legend: ✅ full coverage · 🟡 partial · ➖ not applicable · 🔌 engine handles automatically

## Feature × Example matrix

| Feature | `01_quickstart` | `02_multi_tenant` | `03_fastapi_service` | `04_flask_service` | `05_policy` | `06_pii_tracing` | `demo` | `fastapi-app` | `flask-app` | `django-app` | `rust/axum-app` |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **CoreSDKClient + SDKConfig** | ✅ | ✅ | ✅ | ✅ | ✅ | ➖ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **JWT token validation** | ✅ | ✅ | 🟡 | 🟡 | 🟡 | ➖ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Fail-open / fail-closed** | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | ➖ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **FastAPI middleware** | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ✅ | ✅ | ➖ | ➖ | ➖ |
| **Flask middleware** | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ |
| **Django middleware** | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ |
| **Role-based access control** | ➖ | ➖ | ✅ | ➖ | 🟡 | ➖ | ➖ | ✅ | ✅ | ✅ | ✅ |
| **Attribute-based access control (ABAC)** | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ |
| **Multi-tenant isolation** | ➖ | ✅ | 🟡 | 🟡 | 🟡 | ➖ | ➖ | ✅ | ✅ | ✅ | ✅ |
| **OPA/Rego policy evaluation** | ✅ | ➖ | ➖ | ➖ | ✅ | ➖ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **RBAC policy pattern** | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ | ✅ | ✅ | ✅ | ✅ |
| **ABAC policy pattern** | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ |
| **Rego bundle loading** | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ |
| **Policy audit log** | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |
| **`@trace` decorator** | ➖ | ➖ | ✅ | ➖ | ➖ | ✅ | ➖ | ✅ | ✅ | ✅ | ➖ |
| **PII masking (`mask_value`)** | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ✅ | ➖ | ➖ | ➖ | 🔌 |
| **PII masking (`mask_attributes`)** | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ✅ | ➖ | ➖ | ➖ | 🔌 |
| **`assert_no_pii` (test util)** | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ✅ | ➖ | ➖ | ➖ | ➖ |
| **RFC 9457 error responses** | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Config from `coresdk.toml`** | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ✅ | ✅ | ➖ |
| **Env var config overrides** | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ✅ | ✅ | ✅ |
| **Dockerfile** | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ✅ | ✅ | ✅ |
| **pytest / Rust test suite** | ➖ | ➖ | 🟡 | 🟡 | ➖ | ➖ | ➖ | ✅ | ✅ | ✅ | ✅ |
| **Concurrent requests** | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ |
| **In-process engine (no sidecar)** | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ |
| **Policy engine pool (N threads)** | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ |

## Coverage by example

| Example | Type | Features covered | Best for |
|---|---|---|---|
| `fastapi-app/` | Full project | All 23 (Python) | Starting a new FastAPI service |
| `flask-app/` | Full project | 20 | Starting a new Flask service |
| `django-app/` | Full project | 20 | Starting a new Django REST Framework service |
| `rust/axum-app/` | Full project | All engine features | Rust services embedding `coresdk-engine` directly |
| `policy/` | Rego bundles | RBAC + ABAC + tenant isolation | Authz policy reference |
| `01_quickstart.py` | Script | SDK init, token validation, policy eval | Getting started in 5 min |
| `02_multi_tenant.py` | Script | Multi-tenant client, cross-tenant rejection | Multi-tenant SaaS patterns |
| `03_fastapi_service.py` | Script | FastAPI middleware, RBAC, tracing, RFC 9457, concurrency | FastAPI integration deep-dive |
| `04_flask_service.py` | Script | Flask middleware, tenant scoping | Flask integration deep-dive |
| `05_policy_enforcement.py` | Script | RBAC, ABAC, policy audit log, OPA rules, Rego bundles | Policy patterns reference |
| `06_pii_safe_tracing.py` | Script | PII masking, `@trace`, `assert_no_pii` | Observability + PII guarantees |
| `demo.py` | Script | All SDK primitives, FastAPI middleware | Interactive feature tour |

## Coverage gaps

The following features are not yet demonstrated in any example:

| Feature | Status | Notes |
|---|---|---|
| Flask + RBAC (standalone script) | Partial | `flask-app/` has `require_role`; standalone `04_flask_service.py` does not |
| mTLS SDK↔sidecar config | N/A — automatic | No user config needed in Phase 1b; zero app code required |
| Feature flags (`is_enabled`) | Phase 2 | Lands with `coresdk-flags` crate |
| Rate limiting | Phase 2 | Lands with `coresdk-ratelimit` crate |
| Audit trail | Phase 2 | Lands with `coresdk-audit` crate |
| Go SDK examples | Phase 2 | Go SDK ships Phase 2 |
| TypeScript SDK examples | Phase 2 | TypeScript SDK ships Phase 2 |
| Java SDK examples | Phase 2 | Java SDK ships Phase 2 |
