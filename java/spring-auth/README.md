# Spring Boot + CoreSDK Auth Example

Demonstrates JWT authorization via CoreSDK in a Spring Boot application.

## Prerequisites

- Java 17+
- Maven 3.8+
- CoreSDK sidecar running on `localhost:50051`

## Run

```bash
# Start the sidecar first (see core-sdk README)

# Set env vars (optional — defaults in application.yml)
export CORESDK_SIDECAR_ADDR=localhost:50051
export CORESDK_TENANT_ID=default

# Build and run
mvn spring-boot:run
```

## Test

```bash
# Without token (fail-open returns allowed=true with unknown subject)
curl http://localhost:8081/me

# With Bearer token
curl -H "Authorization: Bearer <your-jwt>" http://localhost:8081/me
```

## Configuration

Edit `src/main/resources/application.yml` or override via environment variables:

| Property | Env var | Default |
|----------|---------|---------|
| `coresdk.endpoint` | `CORESDK_SIDECAR_ADDR` | `localhost:50051` |
| `coresdk.tenant-id` | `CORESDK_TENANT_ID` | `default` |
| `coresdk.fail-mode` | `CORESDK_FAIL_MODE` | `open` |
| `coresdk.control-plane-url` | `CORESDK_CONTROL_PLANE_URL` | `http://localhost:8080` |
