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
pip install "coresdk[fastapi,flask]"
```

---

## Python examples

### `python/fastapi-app/` — Full project (start here)

A complete multi-tenant REST API with **every feature in one place** — FastAPI edition.

```
python/fastapi-app/
  main.py          ← FastAPI app — auth, RBAC, policy, tracing, multi-tenancy
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
| Multi-tenant data isolation | `get_tenant(request)` scopes all DB queries |
| OPA/Rego policy check | `GET /policy/check` → `evaluate_policy()` |
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
```

## Related repos

| Repo | Description |
|---|---|
| [coresdk-dev/core](https://github.com/coresdk-dev/core) | Rust engine + sidecar binary releases |
| [coresdk-dev/sdk-python](https://github.com/coresdk-dev/sdk-python) | Python SDK (`pip install coresdk`) |
| [coresdk-dev/examples](https://github.com/coresdk-dev/examples) | This repo |
