# CoreSDK axum-app — multi-stage Docker build
#
# Stage 1: build the release binary using the official Rust image.
# Stage 2: copy only the binary into a minimal Debian slim image.
#
# No OpenSSL — CoreSDK uses rustls (TLS 1.3 only), so the runtime image
# requires no libssl and stays small (~20 MB).
#
# Usage:
#   docker build -t axum-app .
#   docker run -p 3000:3000 \
#     -e CORESDK_JWKS_URL=https://your-idp/.well-known/jwks.json \
#     -e CORESDK_TENANT_ID=acme \
#     axum-app

# ---------------------------------------------------------------------------
# Stage 1 — builder
# ---------------------------------------------------------------------------
FROM rust:1.82-slim AS builder

# Install build dependencies (no OpenSSL — only needed for linking C libs).
RUN apt-get update && apt-get install -y --no-install-recommends \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy manifests first so Docker layer-caches dependency compilation.
COPY Cargo.toml ./

# Seed a dummy main so `cargo build` can compile dependencies without source.
RUN mkdir src && echo 'fn main(){}' > src/main.rs
RUN cargo build --release 2>/dev/null || true
RUN rm -f src/main.rs

# Copy real source and build.
COPY src/ src/
# Touch main.rs so Cargo knows it changed vs the dummy.
RUN touch src/main.rs
RUN cargo build --release

# ---------------------------------------------------------------------------
# Stage 2 — runtime
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim

# ca-certificates is needed for outbound TLS (JWKS URL fetch, OTLP export).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/axum-app /usr/local/bin/axum-app

# Run as a non-root user.
RUN useradd --no-create-home --shell /bin/false appuser
USER appuser

EXPOSE 3000

# All configuration is via environment variables — see README.md.
CMD ["/usr/local/bin/axum-app"]
