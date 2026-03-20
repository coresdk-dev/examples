# CoreSDK Flask Example

A multi-tenant REST API demonstrating JWT auth, role-based access, OPA policy enforcement, and PII-safe tracing with CoreSDK.

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
# Terminal 1 — start the sidecar
coresdk-sidecar

# Terminal 2 — start the Flask app
flask --app main run --port 5000
```

## Try it

```bash
# No token → 401
curl http://localhost:5000/products

# With token (fail-open without real JWKS)
curl -H "Authorization: Bearer alice-token" http://localhost:5000/products
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
