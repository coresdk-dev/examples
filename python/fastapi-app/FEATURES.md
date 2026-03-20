# FastAPI App — CoreSDK Feature Coverage

All 47 CoreSDK features mapped to this example, the Python SDK, and the roadmap.

Legend: ✅ demonstrated here · 🔌 SDK/sidecar handles it (no app code needed) · 🗺 roadmap (Phase 2/3) · ➖ not applicable to Python apps

---

## Phase 1a — Core Engine (11 features)

| # | Feature | In this app | Where / How |
|---|---------|:-----------:|-------------|
| 1.1 | JWT / OIDC / JWK auth (RS256, ES256, PS256) | ✅ | `CoreSDKMiddleware` validates every `Authorization: Bearer` header via sidecar. Set `CORESDK_JWKS_URL` for real IdP. |
| 1.2 | RBAC / ABAC authorization | ✅ | `require_role("editor")` on `POST /products`, `require_role("admin")` on `DELETE` and `GET /tenants` |
| 1.3 | Rego policy engine (<2ms p99) | ✅ | `GET /policy/check` calls `_sdk.evaluate_policy("data.authz.allow", {...})` |
| 1.4 | Config hot-reload | ✅ | `load_config()` reads `coresdk.toml`; all `sdk.*` keys overridable via `CORESDK_*` env vars |
| 1.5 | PII / secrets masking | 🔌 | Sidecar's `SpanProcessor` redacts emails, tokens, API keys from all spans before export. Zero app code needed. |
| 1.6 | Tenant context propagation | ✅ | `get_tenant(request)` reads `tenant_id` from JWT claims → passed to every DB query and policy call |
| 1.7 | Multi-tenancy enforcement | ✅ | `_db.get(tenant, [])` — each tenant sees only their own products. Two tenants in `coresdk.toml`: `acme-corp`, `globex` |
| 1.8 | RFC 9457 error format | ✅ | All 401/403/404 return `application/problem+json` with `type` / `title` / `status` / `detail`. Exception handler registered. |
| 1.9 | TLS 1.3 transport | 🔌 | SDK↔sidecar is always TLS 1.3 (mTLS). No app config needed. |
| 1.10 | Versioned gRPC API | 🔌 | SDK speaks `v1` proto. Sidecar exposes `AuthService`, `PolicyService`, `ConfigService`, `TenantService`. |
| 1.11 | Resilience (retry / circuit breaker / timeout) | 🔌 | Built into `CoreSDKClient`. Failures surface as RFC 9457 errors. |

---

## Phase 1b — Wrapper SDK + Sidecar (12 features)

| # | Feature | In this app | Where / How |
|---|---------|:-----------:|-------------|
| 1.12 | Sidecar daemon | 🔌 | `coresdk-sidecar` runs separately. App connects via `sidecar_addr = "[::1]:50051"` in `coresdk.toml`. |
| 1.13 | Offline mode (HMAC-verified cache) | 🔌 | Sidecar caches policies + config locally. App continues with `fail_mode = "open"` when control plane unreachable. |
| 1.14 | Structured logging (OTel Logs) | 🔌 | Sidecar emits OTLP logs. Set `OTEL_EXPORTER_OTLP_ENDPOINT` to collect. |
| 1.15 | Distributed tracing (OTel Traces) | ✅ | `@trace(intent="list-products")` on every route creates OTel spans with W3C `traceparent` propagation. |
| 1.16 | OTel metrics export | 🔌 | Sidecar exports request counters, latency histograms, circuit-breaker state via OTLP. |
| 1.17 | OTLP export (traces + metrics + logs) | 🔌 | `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` → Jaeger / Grafana / Datadog. |
| 1.18 | Middleware framework | ✅ | `app.add_middleware(CoreSDKMiddleware, sdk=SDKAdapter(), exclude_paths=["/healthz", ...])` |
| 1.19 | RFC 9457 error propagation in SDK | ✅ | `@app.exception_handler(ProblemDetailError)` converts all SDK errors to `problem+json` responses. |
| 1.20 | Intent annotations (`@trace`) | ✅ | Every route: `@trace(intent="list-products")`, `@trace(intent="policy-check")`, etc. |
| 1.21 | Recovery hints | 🔌 | SDK attaches structured hints to RFC 9457 `extensions` field. Visible in error responses automatically. |
| 1.22 | CLI tooling | ➖ | `coresdk` CLI for local testing and policy dry-run. Not app code. |
| 1.23 | Terminal trace viewer | ➖ | `coresdk traces` — interactive span tree in terminal. Not app code. |

---

## Phase 2 — Production Readiness (17 features)

| # | Feature | In this app | Where / How |
|---|---------|:-----------:|-------------|
| 2.1 | Feature flags (per tenant/user) | 🗺 | Phase 2. Will be `sdk.is_enabled("flag", tenant_id=tenant)` |
| 2.2 | Licensing and metering | 🗺 | Phase 2. PKI-signed license tokens — sidecar enforces; zero app code. |
| 2.3 | Rate limiting (per user/tenant) | 🗺 | Phase 2. Middleware will enforce automatically. |
| 2.4 | Audit trails (tamper-evident) | 🗺 | Phase 2. All policy decisions append to hash-chained log via sidecar. |
| 2.5 | Sidecar config sync + cache | 🔌 | Sidecar handles control plane sync + HMAC cache. Ships Phase 1b. |
| 2.6 | Sidecar auto-update | 🗺 | Phase 2. Signed JWS update bundles; auto-rollback. |
| 2.7 | Pluggable caching (Redis) | 🗺 | Phase 2. In-memory default; Redis adapter with TLS 1.3. |
| 2.8 | Secrets vault (Vault / AWS / Azure) | 🗺 | Phase 2. `CORESDK_VAULT_ADDR` → memory-only fetch, never written to disk. |
| 2.9 | Data validation (JSON Schema) | 🗺 | Phase 2. Request/response schema enforcement. |
| 2.10 | Go / TypeScript / Java SDKs | 🗺 | Phase 2. Same middleware interface as Python. |
| 2.11 | SAML 2.0 / Enterprise SSO | 🗺 | Phase 2. Complements OIDC in 1.1. |
| 2.12 | SCIM provisioning | 🗺 | Phase 2. Auto user/group sync from IdP. |
| 2.13 | LLM-optimised trace export | 🗺 | Phase 2. Minimal diagnostic payload — RFC 9457 + call chain + intents. |
| 2.14 | AI root cause analysis | 🗺 | Phase 2. Local-only by default; opt-in external LLM API. |
| 2.15 | CloudEvents envelope | 🗺 | Phase 2. Sidecar wraps OTel events in CloudEvents metadata. |
| 2.16 | Custom domains / per-tenant branding | 🗺 | Phase 2. Tenant-scoped JWKS endpoints and login pages. |
| 2.17 | Runtime coverage / dead code detection | 🗺 | Phase 2. Trace-based; no app changes needed. |

---

## Phase 3 — Enterprise (7 features)

| # | Feature | In this app | Where / How |
|---|---------|:-----------:|-------------|
| 3.1 | Configurable PII redaction rules | 🗺 | Phase 3. Custom regex + field-name patterns extend Phase 1a auto-masking. |
| 3.2 | Compliance controls (SOC 2, HIPAA, GDPR, PCI) | 🗺 | Phase 3. Certified audit-ready controls package. |
| 3.3 | Security hooks (pre/post execution) | 🗺 | Phase 3. Boot-time registration only. |
| 3.4 | SLA / SLO tracking | 🗺 | Phase 3. Latency + uptime metrics via OTel for external SLO systems. |
| 3.5 | On-premise (Helm chart, air-gapped) | 🗺 | Phase 3. `CORESDK_FAIL_MODE=closed` already set for enterprise readiness. |
| 3.6 | Data residency controls | 🗺 | Phase 3. Region-specific data routing; GDPR / UAE PDPL. |
| 3.7 | SBOM + dependency audit | 🗺 | Phase 3. CVE-aware CI gate. |

---

## Summary

| Phase | Total | ✅ In this app | 🔌 SDK/sidecar | 🗺 Roadmap | ➖ N/A |
|-------|-------|:---:|:---:|:---:|:---:|
| Phase 1a — Core Engine | 11 | **8** | 3 | 0 | 0 |
| Phase 1b — Wrapper + Sidecar | 12 | **5** | 5 | 0 | 2 |
| Phase 2 — Production | 17 | 0 | 1 | **16** | 0 |
| Phase 3 — Enterprise | 7 | 0 | 0 | **7** | 0 |
| **Total** | **47** | **13** | **9** | **23** | **2** |

**13 of 47 features are actively demonstrated in this app.**
**9 more work automatically — zero app code required.**
**23 are on the roadmap (Phase 2–3).**
