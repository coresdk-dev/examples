# axum-app — CoreSDK Rust example

Complete Axum REST API demonstrating `coresdk-engine` embedded directly in a
Rust service.  No sidecar required — auth, policy, masking, and tracing all
run in-process.

## Why Rust embeds vs Python using a sidecar

| | Rust (`coresdk-engine`) | Python (`coresdk` PyPI) |
|---|---|---|
| Engine location | In-process Rust crate | Remote gRPC sidecar |
| Auth call latency | ~0 µs (no network) | ~0.5 ms loopback gRPC |
| Deploy complexity | Single binary | Binary + sidecar container |
| Policy pool | N `regorus::Engine` threads | Forwarded to sidecar |
| Recommended for | Latency-critical, Rust services | Python/FastAPI services |

Both approaches expose the same conceptual API: `authorize()`, `evaluate_policy()`,
`mask()`.  The Rust path calls them as ordinary async methods; the Python SDK
calls the sidecar over mTLS gRPC.

## Install

```bash
# From crates.io (once published):
cargo add coresdk-engine

# Or reference the local workspace:
# coresdk-engine = { path = "/path/to/core/crates/coresdk-engine" }
```

## Run

```bash
RUST_LOG=info cargo run
```

The server binds on `:3000` by default.  Override with `PORT=8080 cargo run`.

## Try it

```bash
# Public endpoint — no auth required
curl http://localhost:3000/healthz

# Protected endpoints — require a valid JWT
export TOKEN="<your-jwt>"

# Who am I?
curl -H "Authorization: Bearer $TOKEN" http://localhost:3000/me

# List products (scoped to caller's tenant)
curl -H "Authorization: Bearer $TOKEN" http://localhost:3000/products

# Get a single product (policy-gated via Rego)
curl -H "Authorization: Bearer $TOKEN" http://localhost:3000/products/123

# Ad-hoc policy check
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"action":"read","resource":"products/123"}' \
     http://localhost:3000/policy/check
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `CORESDK_JWKS_URL` | — | Remote JWK Set URL for JWT signature verification |
| `CORESDK_AUDIENCE` | — | Expected `aud` claim (omit to skip audience check) |
| `CORESDK_TENANT_ID` | `default` | Fallback tenant if not present in JWT |
| `CORESDK_SERVICE_NAME` | `unknown-service` | OTel `service.name` resource attribute |
| `CORESDK_FAIL_MODE` | `open` | `open`: bad tokens pass through; `closed`: reject |
| `CORESDK_SIDECAR_ADDR` | `localhost:50051` | Sidecar address (unused for in-process Rust) |
| `CORESDK_ENV` | — | Set to `development` to enable dev-mode logging |
| `CORESDK_POLICY_POOL_SIZE` | `min(cpus, 8)` | Rego engine pool size |
| `PORT` | `3000` | HTTP listen port |
| `RUST_LOG` | `info` | `tracing-subscriber` filter |

## Routes

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/healthz` | None | Liveness check |
| `GET` | `/me` | JWT | Caller identity from JWT claims |
| `GET` | `/products` | JWT | Tenant-scoped product list |
| `GET` | `/products/:id` | JWT + Rego | Single product, policy-gated |
| `POST` | `/policy/check` | JWT + Rego | Ad-hoc policy evaluation |

## Error format

All error responses use RFC 9457 `application/problem+json`:

```json
{
  "type": "https://coresdk.io/errors/unauthorized",
  "title": "Unauthorized",
  "status": 401,
  "detail": "Missing Authorization header"
}
```

## Docker

```bash
docker build -t axum-app .
docker run -p 3000:3000 \
  -e CORESDK_JWKS_URL=https://your-idp/.well-known/jwks.json \
  -e CORESDK_TENANT_ID=acme \
  axum-app
```

## Architecture

```
HTTP request
    │
    ▼
Tower TraceLayer          ← logs method/path/status/latency via tracing
    │
    ▼
auth_middleware           ← extracts Bearer token
    │                        calls engine.authorize() → AuthDecision
    │                        injects Principal extension
    ▼
Route handler             ← reads Principal from request extensions
    │                        calls engine.evaluate_policy() for resource-level checks
    │                        returns JSON or RFC 9457 ProblemDetail
    ▼
HTTP response
```

The `Engine` is initialised once in `main()` and shared via `Arc<AppState>`.
The policy engine pool (`Arc<PolicyEnginePool>`) holds N independent
`regorus::Engine` instances — one per blocking thread — so policy evaluation
never contends on a single mutex at high RPS.
