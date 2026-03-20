# CoreSDK Django Example

A Django REST Framework API demonstrating CoreSDK middleware for JWT auth, multi-tenant isolation, and PII-safe tracing.

## Quick Start

### 1. Install dependencies

```bash
cd examples/python/django-app
pip install -r requirements.txt
```

This installs `coresdk[django]`, `djangorestframework`, `gunicorn`, `pytest`, and `pytest-django`.

### 2. Set environment variables

```bash
export CORESDK_SIDECAR_ADDR="[::1]:50051"
export CORESDK_TENANT_ID="acme-corp"
export CORESDK_FAIL_MODE="open"
export DJANGO_SETTINGS_MODULE="api.settings"
```

Or edit `coresdk.toml` in this directory to change defaults.

### 3. Start the sidecar

```bash
# In a separate terminal
coresdk-sidecar

# Or via Docker
docker run -p 50051:50051 ghcr.io/coresdk-dev/sidecar:latest
```

### 4. Run the Django app

```bash
python manage.py runserver 8000
```

For production:

```bash
gunicorn api.wsgi:application -b 0.0.0.0:8000
```

### 5. Test with curl

```bash
# Health check (no auth required)
curl http://localhost:8000/healthz/

# No token -- returns 401
curl -i http://localhost:8000/api/products/

# With token (fail-open without real JWKS)
curl -H "Authorization: Bearer alice-token" http://localhost:8000/api/products/

# Create a product
curl -X POST http://localhost:8000/api/products/ \
  -H "Authorization: Bearer alice-token" \
  -H "Content-Type: application/json" \
  -d '{"name": "Widget C", "price": 49.99}'
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CORESDK_SIDECAR_ADDR` | `[::1]:50051` | Sidecar gRPC address |
| `CORESDK_TENANT_ID` | `default` | Default tenant |
| `CORESDK_FAIL_MODE` | `open` | `open` or `closed` |
| `DJANGO_SETTINGS_MODULE` | `api.settings` | Django settings module |

Configuration can also be set in `coresdk.toml`.

## Project Structure

```
django-app/
  manage.py          # Django CLI entry point
  coresdk.toml       # CoreSDK configuration
  requirements.txt   # Python dependencies
  test_app.py        # Tests
  api/               # Django app package
```

## Tests

```bash
pytest test_app.py -v
```
