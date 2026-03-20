# CoreSDK Examples

Copy-paste examples for every CoreSDK feature. Each is self-contained — clone, install, run.

## Setup (once)

```bash
# 1. Download & start the sidecar
curl -Lo coresdk-sidecar \
  https://github.com/coresdk-dev/core/releases/latest/download/coresdk-sidecar-darwin-arm64
chmod +x coresdk-sidecar && sudo mv coresdk-sidecar /usr/local/bin/
coresdk-sidecar &

# 2. Install the Python SDK
pip install "coresdk[fastapi]"
```

---

## Python examples

### `python/fastapi-app/` — Full project (start here)

A complete multi-tenant REST API with **every feature in one place**.

```
python/fastapi-app/
  main.py          ← FastAPI app — auth, RBAC, policy, tracing, multi-tenancy
  coresdk.toml     ← config: sidecar address, tenants, policy, OTEL
  test_app.py      ← pytest suite (13 tests, all passing)
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
python python/03_fastapi_service.py    # built-in test harness (9/9)
uvicorn python.03_fastapi_service:app  # as a real server
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

### `python/06_pii_safe_tracing.py` — PII masking + @trace (23/23)

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
Your App
   │
   ├── pip install coresdk
   │        │  gRPC  [::1]:50051
   │        ▼
   │   coresdk-sidecar   ←── Rego bundles, JWK sets, HMAC keys
   │        │  OTel
   │        ▼
   │   your collector (Grafana / Datadog / Jaeger / ...)
```
