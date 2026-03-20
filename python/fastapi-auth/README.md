# FastAPI Auth Example

JWT authentication on FastAPI in under 10 lines.

## Run

```bash
pip install coresdk fastapi uvicorn
export CORESDK_JWKS_URL=https://your-idp/.well-known/jwks.json
uvicorn main:app --reload
```

## Try it

```bash
# Protected route — returns 401 without token
curl http://localhost:8000/me

# With a valid JWT
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/me
# → {"user_id": "alice", "tenant": "acme", "roles": ["user"]}

# Admin-only route
curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8000/admin
# → {"message": "Hello admin alice"}
```

## What CoreSDK does automatically

- Fetches and hot-reloads JWK sets (no restart needed on key rotation)
- Validates RS256 / ES256 / PS256 signatures
- Extracts tenant ID, roles, and standard claims
- Redacts any PII from trace spans before export
