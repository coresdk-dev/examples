# CoreSDK Axum Integration Example

This is the reference integration used for the Phase 1a design partner gate.

## Run

```bash
# Set env vars
export CORESDK_ENV=development
export CORESDK_TENANT_ID=my-tenant

cargo run
```

## Test

```bash
# Health check
curl http://localhost:3000/health

# Protected route — no token
curl http://localhost:3000/protected
# → 401 application/problem+json

# Protected route — with token (dev mode: any non-empty token passes)
curl -H "Authorization: Bearer test-token" http://localhost:3000/protected
# → 200 {"message":"authenticated!"}
```
