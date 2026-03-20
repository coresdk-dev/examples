# CoreSDK Examples

Practical, copy-paste examples for every language. Each example is self-contained — clone, set one env var, run.

## Examples

| Example | Language | What it shows |
|---|---|---|
| [fastapi-auth](./python/fastapi-auth/) | Python | JWT auth middleware on FastAPI |
| [fastapi-policy](./python/fastapi-policy/) | Python | Rego policy enforcement on FastAPI routes |
| [django-multitenant](./python/django-multitenant/) | Python | Per-tenant isolation in Django |
| [axum-auth](./rust/axum-auth/) | Rust | Tower middleware for JWT + policy on Axum |
| [axum-otel](./rust/axum-otel/) | Rust | OpenTelemetry tracing with zero-PII spans |
| [gin-auth](./go/gin-auth/) | Go | Auth middleware on Gin |
| [grpc-client](./go/grpc-client/) | Go | Connect to sidecar over mTLS gRPC |
| [express-auth](./typescript/express-auth/) | TypeScript | JWT middleware on Express |
| [nextjs-edge](./typescript/nextjs-edge/) | TypeScript | Edge-compatible auth for Next.js |
| [spring-boot](./java/spring-boot/) | Java | Spring Boot starter auto-configuration |

## Quick Start (any example)

```bash
git clone git@github.com:coresdk-dev/examples.git
cd examples/<language>/<example>

# Set sidecar address (or use embedded mode)
export CORESDK_SIDECAR_ADDR=localhost:50051

# Run
<see example README>
```

## Architecture

```
Your App
   │
   ├── CoreSDK SDK (language-native)
   │        │  gRPC + mTLS
   │        ▼
   │   CoreSDK Sidecar  ←── policy bundles, JWK sets, config
   │        │
   │        ▼
   │   OTel Collector → your observability backend
```
