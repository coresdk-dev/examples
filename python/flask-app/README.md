# CoreSDK Flask Example

A multi-tenant REST API demonstrating JWT auth, role-based access, OPA policy enforcement, and PII-safe tracing with CoreSDK.

## Quick Start

### 1. Install dependencies

```bash
cd examples/python/flask-app
pip install -r requirements.txt
```

This installs `coresdk[flask]`, `gunicorn`, and `pytest`.

### 2. Set environment variables

```bash
export CORESDK_SIDECAR_ADDR="[::1]:50051"
export CORESDK_TENANT_ID="acme-corp"
export CORESDK_FAIL_MODE="open"
```

Or edit `coresdk.toml` in this directory to change defaults.

### 3. Start the sidecar

```bash
# In a separate terminal
coresdk-sidecar

# Or via Docker
docker run -p 50051:50051 ghcr.io/coresdk-dev/sidecar:latest
```

### 4. Run the Flask app

```bash
flask --app main run --port 5000
```

For production:

```bash
gunicorn main:app -b 0.0.0.0:5000
```

### 5. Test with curl

```bash
# Health check (no auth required)
curl http://localhost:5000/healthz

# No token -- returns 401
curl -i http://localhost:5000/products

# With token (fail-open without real JWKS)
curl -H "Authorization: Bearer alice-token" http://localhost:5000/products

# Get current user claims
curl -H "Authorization: Bearer alice-token" http://localhost:5000/me

# Create a product (requires editor role)
curl -X POST http://localhost:5000/products \
  -H "Authorization: Bearer alice-token" \
  -H "Content-Type: application/json" \
  -d '{"name": "Widget C", "price": 49.99}'

# Evaluate a policy rule
curl -H "Authorization: Bearer alice-token" \
  "http://localhost:5000/policy/check?action=read&resource=reports"
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CORESDK_SIDECAR_ADDR` | `[::1]:50051` | Sidecar gRPC address |
| `CORESDK_TENANT_ID` | `default` | Default tenant |
| `CORESDK_FAIL_MODE` | `open` | `open` or `closed` |
| `CORESDK_SERVICE_NAME` | `flask-example` | Service name for tracing |
| `CORESDK_DEV_MODE` | `true` | Dev mode bypass |

Configuration can also be set in `coresdk.toml`.

## Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/healthz` | No | Health check |
| GET | `/me` | Yes | Current user claims |
| GET | `/tenants` | Yes (admin) | List configured tenants |
| GET | `/products` | Yes | List products (tenant-scoped) |
| GET | `/products/:id` | Yes | Get product |
| POST | `/products` | Yes (editor) | Create product |
| DELETE | `/products/:id` | Yes (admin) | Delete product |
| GET | `/policy/check` | Yes | Evaluate a Rego policy rule |

## Tests

```bash
pytest test_app.py -v
```
