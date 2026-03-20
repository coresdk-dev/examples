# CoreSDK Django Example

A Django REST Framework API demonstrating CoreSDK middleware for JWT auth, multi-tenant isolation, and PII-safe tracing.

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
# Terminal 1 — start the sidecar
coresdk-sidecar

# Terminal 2 — start the Django app
python manage.py runserver 8000
```

## Try it

```bash
# No token → 401
curl http://localhost:8000/api/products/

# With token (fail-open without real JWKS)
curl -H "Authorization: Bearer alice-token" http://localhost:8000/api/products/
```

## Configuration

Edit `coresdk.toml` or set environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CORESDK_SIDECAR_ADDR` | `[::1]:50051` | Sidecar gRPC address |
| `CORESDK_TENANT_ID` | `default` | Default tenant |
| `CORESDK_FAIL_MODE` | `open` | `open` or `closed` |

## Tests

```bash
pytest test_app.py -v
```
