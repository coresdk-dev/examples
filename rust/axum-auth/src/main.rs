//! CoreSDK — Axum JWT auth example.
//!
//! Demonstrates direct embedding of `coresdk-engine` for auth-only use cases.
//! No sidecar required: auth runs in-process via `Engine::from_env()`.
//!
//! # Quick start
//!
//! ```bash
//! cargo run
//! curl http://localhost:3000/healthz
//! curl -H "Authorization: Bearer <your-jwt>" http://localhost:3000/me
//! curl -H "Authorization: Bearer <your-jwt>" http://localhost:3000/admin
//! ```

use std::sync::Arc;

use axum::{
    extract::{Request, State},
    http::{HeaderMap, StatusCode},
    middleware::{self, Next},
    response::{IntoResponse, Response},
    routing::get,
    Json, Router,
};
use serde_json::json;
use tracing::{error, info, warn};

use coresdk_engine::{
    auth::decision::{AuthDecision, AuthRequest},
    Engine,
};

#[derive(Clone)]
struct AppState {
    engine: Arc<Engine>,
}

#[derive(Debug, Clone)]
struct Principal {
    subject: String,
    tenant_id: String,
    roles: Vec<String>,
}

impl Principal {
    fn has_role(&self, role: &str) -> bool {
        self.roles.iter().any(|r| r == role)
    }
}

async fn auth_middleware(
    State(state): State<AppState>,
    mut req: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    let token = req
        .headers()
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or(StatusCode::UNAUTHORIZED)?;

    let auth_req = AuthRequest {
        token: token.to_owned(),
        expected_audience: std::env::var("CORESDK_AUDIENCE").ok(),
        tenant_id: std::env::var("CORESDK_TENANT_ID").unwrap_or_else(|_| "default".into()),
    };

    let decision: AuthDecision = state.engine.authorize(auth_req).map_err(|e| {
        error!(error = %e, "Auth engine error");
        StatusCode::SERVICE_UNAVAILABLE
    })?;

    if !decision.allowed {
        warn!("Token rejected");
        return Err(StatusCode::UNAUTHORIZED);
    }

    let principal = Principal {
        subject: decision.subject.unwrap_or_else(|| "anonymous".into()),
        tenant_id: std::env::var("CORESDK_TENANT_ID").unwrap_or_else(|_| "default".into()),
        roles: decision.roles,
    };

    req.extensions_mut().insert(principal);
    Ok(next.run(req).await)
}

async fn healthz() -> Json<serde_json::Value> {
    Json(json!({ "status": "ok" }))
}

async fn me(req: Request) -> Result<Json<serde_json::Value>, StatusCode> {
    let principal = req
        .extensions()
        .get::<Principal>()
        .ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(json!({
        "subject":   principal.subject,
        "tenant_id": principal.tenant_id,
        "roles":     principal.roles,
    })))
}

async fn admin(req: Request) -> Result<Json<serde_json::Value>, StatusCode> {
    let principal = req
        .extensions()
        .get::<Principal>()
        .ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;

    if !principal.has_role("admin") {
        return Err(StatusCode::FORBIDDEN);
    }

    Ok(Json(json!({
        "message": format!("hello admin {}", principal.subject),
    })))
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .init();

    let engine = Engine::from_env()?;
    let state = AppState {
        engine: Arc::clone(&engine),
    };

    let public = Router::new().route("/healthz", get(healthz));

    let protected = Router::new()
        .route("/me", get(me))
        .route("/admin", get(admin))
        .route_layer(middleware::from_fn_with_state(state.clone(), auth_middleware));

    let app = Router::new()
        .merge(public)
        .merge(protected)
        .with_state(state);

    let addr = "0.0.0.0:3000";
    let listener = tokio::net::TcpListener::bind(addr).await?;
    info!(addr = %addr, "Listening");
    axum::serve(listener, app).await?;

    Ok(())
}
