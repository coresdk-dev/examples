# CoreSDK Examples

[![SDK](https://img.shields.io/pypi/v/coresdk.svg?label=pip+install+coresdk)](https://pypi.org/project/coresdk/)
[![Sidecar](https://img.shields.io/github/v/release/coresdk-dev/core?label=sidecar)](https://github.com/coresdk-dev/core/releases)

Copy-paste examples for every CoreSDK feature. Each is self-contained — clone, install, run.

## Setup (once)

```bash
# 1. Download & start the sidecar
# macOS (Apple Silicon)
curl -LO https://github.com/coresdk-dev/core/releases/latest/download/coresdk-sidecar-aarch64-apple-darwin.tar.gz
tar xf coresdk-sidecar-aarch64-apple-darwin.tar.gz
./coresdk-sidecar &

# Linux (amd64)
curl -LO https://github.com/coresdk-dev/core/releases/latest/download/coresdk-sidecar-x86_64-unknown-linux-gnu.tar.gz
tar xf coresdk-sidecar-x86_64-unknown-linux-gnu.tar.gz
./coresdk-sidecar &

# Or via Docker (all platforms)
docker run -d -p 50051:50051 ghcr.io/coresdk-dev/sidecar:latest

# 2. Install the Python SDK
pip install "coresdk[fastapi,flask,django]"
```

---

## Python examples

### `python/fastapi-app/` — Full project (start here)

A complete multi-tenant REST API with **every feature in one place** — FastAPI edition.
Includes an ABAC-gated `GET /documents/{doc_id}` route demonstrating attribute-based access control.

```
python/fastapi-app/
  main.py          ← FastAPI app — auth, RBAC, ABAC, policy, tracing, multi-tenancy
  coresdk.toml     ← config: sidecar address, tenants, policy, OTEL
  test_app.py      ← pytest suite (13 tests)
  requirements.txt
  Dockerfile
```

```bash
cd python/fastapi-app
pip install -r requirements.txt
uvicorn main:app --reload
# → http://localhost:8000/docs
```

| Feature | How |
|---|---|
| JWT auth on every route | `CoreSDKMiddleware` |
| Role-based access control | `require_role("editor")` / `require_role("admin")` |
| Attribute-based access control | `GET /documents/{doc_id}` — Rego checks `input.user.department` |
| Multi-tenant data isolation | `get_tenant(request)` scopes all DB queries |
| OPA/Rego policy check | `GET /policy/check` → `evaluate_policy()` |
| Rego bundle loading | `CORESDK_POLICY_DIR` → loads `policy/authz.rego` bundle |
| PII-safe tracing | `@trace(intent=...)` on every route |
| RFC 9457 errors | 401/403/404 → `application/problem+json` |
| Config file + env overrides | `coresdk.toml` + `CORESDK_*` env vars |

---

### `python/flask-app/` — Full project (Flask edition)

Same feature set as `fastapi-app`, built with Flask + Gunicorn.

```
python/flask-app/
  main.py          ← Flask app — auth, RBAC, policy, tracing, multi-tenancy
  coresdk.toml     ← config: sidecar address, tenants, policy, OTEL
  test_app.py      ← pytest suite (11 tests)
  requirements.txt
  Dockerfile
```

```bash
cd python/flask-app
pip install -r requirements.txt
flask --app main run --port 5000
# → http://localhost:5000
```

| Feature | How |
|---|---|
| JWT auth on every route | `CoreSDKMiddleware(app, sdk=...)` |
| Role-based access control | `@require_role("editor")` decorator |
| Multi-tenant data isolation | `get_tenant()` reads `g.claims.tenant_id` |
| OPA/Rego policy check | `GET /policy/check` → `evaluate_policy()` |
| PII-safe tracing | `@trace(intent=...)` on every route |
| RFC 9457 errors | 401/403/404 → `application/problem+json` |
| Config file + env overrides | `coresdk.toml` + `CORESDK_*` env vars |

---

### `python/django-app/` — Full project (Django REST Framework edition)

Same feature set as `fastapi-app` and `flask-app`, built with Django REST Framework.
JWT claims are stored on `request.coresdk_claims` by the middleware.

```
python/django-app/
  api/
    views.py       ← DRF views — auth, RBAC, policy, tracing, multi-tenancy
    urls.py        ← URL routing
    settings.py    ← Django settings with CoreSDK config block
  manage.py
  coresdk.toml     ← config: sidecar address, tenants, policy, OTEL
  test_app.py      ← pytest suite (11 tests)
  requirements.txt
  Dockerfile
```

```bash
cd python/django-app
pip install -r requirements.txt
python manage.py runserver 8080
# → http://localhost:8080
```

| Feature | How |
|---|---|
| JWT auth on every route | `MIDDLEWARE = ["coresdk.django.CoreSDKMiddleware", ...]` |
| Role-based access control | `@require_role("editor")` decorator |
| Multi-tenant data isolation | `request.coresdk_claims["tenant_id"]` scopes DB queries |
| OPA/Rego policy check | `GET /policy/check` → `evaluate_policy()` |
| PII-safe tracing | `@trace(intent=...)` on every view |
| RFC 9457 errors | 401/403/404 → `application/problem+json` |
| Config file + env overrides | `coresdk.toml` + `CORESDK_*` env vars |

---

### `python/01_quickstart.py` — Minimal SDK usage (10 lines)

```bash
python python/01_quickstart.py
```

Connect to sidecar, validate a token, evaluate a policy.

---

### `python/02_multi_tenant.py` — One client per tenant

```bash
python python/02_multi_tenant.py
```

Separate `CoreSDKClient` per tenant (`acme-corp`, `globex`, `initech`). Shows cross-tenant rejection.

---

### `python/03_fastapi_service.py` — FastAPI document service

```bash
python python/03_fastapi_service.py    # built-in test harness
```

Tenant-scoped document CRUD, role guards, RFC 9457 errors, 10 concurrent requests.

---

### `python/04_flask_service.py` — Flask product service

```bash
python python/04_flask_service.py
```

Same patterns as 03 but with Flask + `CoreSDKFlask`.

---

### `python/05_policy_enforcement.py` — Policy evaluation patterns

```bash
python python/05_policy_enforcement.py
```

RBAC + ABAC calls to `evaluate_policy()` with a full audit log.
Load a Rego bundle via `CORESDK_POLICY_DIR` for real enforcement.

---

### `python/06_pii_safe_tracing.py` — PII masking + @trace

```bash
python python/06_pii_safe_tracing.py
```

`mask_value()`, `mask_attributes()`, `assert_no_pii()`, `@trace` — guarantees no PII in spans.

---

## Rust examples

### `rust/axum-app/` — Axum REST API (coresdk-engine embedded)

A complete Axum REST API demonstrating `coresdk-engine` embedded **directly in the Rust process** — no sidecar required. Auth, policy evaluation (regorus engine pool), PII masking, and tracing all run in-process.

```
rust/axum-app/
  src/
    main.rs        ← Axum app — auth middleware, policy pool, RFC 9457 errors
  Cargo.toml
  Dockerfile
```

```bash
cd rust/axum-app
RUST_LOG=info cargo run
# → http://localhost:3000
```

| Feature | How |
|---|---|
| In-process auth | `engine.authorize()` called directly — no gRPC hop |
| Rego policy pool | N `regorus::Engine` instances, one per blocking thread |
| Role-based access control | `require_role` Tower layer |
| RFC 9457 errors | All error responses use `application/problem+json` |
| OTel tracing | Tower `TraceLayer` + `tracing-subscriber` |
| Concurrent requests | Tokio async; policy pool prevents mutex contention |
| Env var config | `CORESDK_*` env vars; `PORT` for listen address |

See [`rust/axum-app/README.md`](rust/axum-app/README.md) for full route listing and Docker instructions.

---

## Policy bundles

### `policy/` — Rego bundle reference

Production-ready Rego policies for loading via `CORESDK_POLICY_DIR`.

```
policy/
  authz.rego              ← RBAC + ABAC bundle (data.authz.allow)
  tenant_isolation.rego   ← tenant isolation policy (data.tenants.allowed)
  README.md               ← bundle loading guide
```

Load in any example:

```bash
export CORESDK_POLICY_DIR=./policy
python python/fastapi-app/main.py   # or any other example
```

The `fastapi-app` ABAC route (`GET /documents/{doc_id}`) evaluates `data.authz.allow` against `authz.rego`.
See [`policy/README.md`](policy/README.md) for bundle structure and dry-run instructions.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `CORESDK_SIDECAR_ADDR` | `[::1]:50051` | Sidecar gRPC address |
| `CORESDK_TENANT_ID` | `acme-corp` | Default tenant |
| `CORESDK_SERVICE_NAME` | *(app name)* | Service name in traces |
| `CORESDK_FAIL_MODE` | `open` | `open` = allow on sidecar error · `closed` = deny |
| `CORESDK_JWKS_URL` | — | Your IdP JWKS URL for real JWT validation |
| `CORESDK_POLICY_DIR` | — | Path to Rego bundle for real policy enforcement |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | OTel collector endpoint for trace export |

## Architecture

```
Your App (Python / Go / TypeScript / Java)
   │
   ├── pip install coresdk
   │        │  gRPC/mTLS  [::1]:50051
   │        ▼
   │   coresdk-sidecar   ←── Rego bundles, JWK sets, HMAC keys
   │        │  OTel
   │        ▼
   │   your collector (Grafana / Datadog / Jaeger / ...)

Your App (Rust)
   │
   ├── cargo add coresdk-engine
   │        │  in-process (no network)
   │        ▼
   │   coresdk-engine   ←── Rego engine pool, JWK cache, PII masking
```

## Related repos

| Repo | Description |
|---|---|
| [coresdk-dev/core](https://github.com/coresdk-dev/core) | Rust engine + sidecar binary releases |
| [coresdk-dev/sdk-python](https://github.com/coresdk-dev/sdk-python) | Python SDK (`pip install coresdk`) |
| [coresdk-dev/examples](https://github.com/coresdk-dev/examples) | This repo |
