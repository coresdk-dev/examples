# FastAPI App — CoreSDK Example

A complete multi-tenant REST API showing every CoreSDK feature in one project.

## Features demonstrated

| Feature | Where |
|---|---|
| JWT auth (all routes protected) | `CoreSDKMiddleware` in `main.py` |
| Role-based access control | `require_role("editor")` / `require_role("admin")` |
| Multi-tenant data isolation | `get_tenant(request)` scopes all DB queries |
| OPA/Rego policy check | `GET /policy/check` calls `evaluate_policy()` |
| PII-safe tracing | `@trace(intent=...)` on every route |
| RFC 9457 error responses | 401/403/404 all return structured problem+json |
| Config from file + env vars | `coresdk.toml` + `CORESDK_*` env var overrides |

## Quick start

```bash
# 1. Start the sidecar (download from github.com/coresdk-dev/core/releases)
coresdk-sidecar &

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the API
uvicorn main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

## Try it

```bash
# No token → 401
curl http://localhost:8000/products

# With token → 200 (fail-open without real JWKS)
curl -H "Authorization: Bearer alice-token" http://localhost:8000/products

# Who am I?
curl -H "Authorization: Bearer alice-token" http://localhost:8000/me

# Get a product
curl -H "Authorization: Bearer alice-token" http://localhost:8000/products/1

# Policy check
curl -H "Authorization: Bearer alice-token" \
  "http://localhost:8000/policy/check?action=read&resource=reports/q4"

# Create product (needs 'editor' role in JWT — fails in fail-open mode)
curl -X POST http://localhost:8000/products \
  -H "Authorization: Bearer alice-token" \
  -H "Content-Type: application/json" \
  -d '{"name": "Widget C", "price": 199.00}'
```

## Run tests

```bash
pytest test_app.py -v
```

## Configuration

Edit `coresdk.toml` to configure tenants, sidecar address, policy rules.

Override any setting with environment variables:

```bash
CORESDK_SIDECAR_ADDR=10.0.0.1:50051 \
CORESDK_TENANT_ID=my-company \
CORESDK_FAIL_MODE=closed \
uvicorn main:app
```

## Production checklist

- [ ] Set `CORESDK_JWKS_URL` to your IdP's JWKS endpoint for real JWT validation
- [ ] Set `CORESDK_FAIL_MODE=closed` to deny on sidecar errors
- [ ] Load a Rego bundle: set `bundle_dir` in `coresdk.toml`
- [ ] Set `OTEL_EXPORTER_OTLP_ENDPOINT` for trace export
- [ ] Set `CORESDK_CACHE_HMAC_KEY` on the sidecar for cache integrity
