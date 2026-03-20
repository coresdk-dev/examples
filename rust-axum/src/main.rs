//! CoreSDK design-partner reference integration.
//!
//! This is what a design partner sees when they `cargo add coresdk-engine`:
//! - Engine::from_env() initializes auth + policy + config
//! - axum middleware enforces auth on protected routes
//! - RFC 9457 errors returned on deny
//! - All PII scrubbed before any logging

use axum::{
    extract::{Request, State},
    http::StatusCode,
    middleware::{self, Next},
    response::{IntoResponse, Json, Response},
    routing::get,
    Router,
};
use coresdk_engine::{AuthRequest, Engine, EngineError};
use std::sync::Arc;
use tracing::info;

#[derive(Clone)]
struct AppState {
    sdk: Arc<Engine>,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt().init();

    // One line to initialize: reads CORESDK_* env vars
    let engine = Engine::from_env()?;
    let state = AppState { sdk: engine };

    let app = Router::new()
        .route("/protected", get(protected_handler))
        .layer(middleware::from_fn_with_state(
            state.clone(),
            auth_middleware,
        ))
        .route("/health", get(health_handler))
        .with_state(state);

    let addr = "0.0.0.0:3000";
    info!("Listening on {addr}");
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;
    Ok(())
}

async fn auth_middleware(State(state): State<AppState>, request: Request, next: Next) -> Response {
    let token = request
        .headers()
        .get("Authorization")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .unwrap_or("")
        .to_string();

    if token.is_empty() {
        return problem_detail(401, "Unauthorized", "Missing Bearer token");
    }

    let auth_req = AuthRequest {
        token,
        expected_audience: None,
        tenant_id: std::env::var("CORESDK_TENANT_ID").unwrap_or_default(),
    };

    match state.sdk.authorize(auth_req) {
        Ok(decision) if decision.allowed => next.run(request).await,
        Ok(_) => problem_detail(403, "Forbidden", "Policy denied"),
        Err(EngineError::Auth(e)) => problem_detail(401, "Unauthorized", &e.to_string()),
        Err(e) => problem_detail(500, "Internal Error", &e.to_string()),
    }
}

async fn protected_handler() -> Json<serde_json::Value> {
    Json(serde_json::json!({ "message": "authenticated!", "status": "ok" }))
}

async fn health_handler() -> StatusCode {
    StatusCode::OK
}

fn problem_detail(status: u16, title: &str, detail: &str) -> Response {
    let body = serde_json::json!({
        "type": format!("https://coresdk.io/errors/{}", title.to_lowercase().replace(' ', "-")),
        "title": title,
        "status": status,
        "detail": detail,
    });
    (
        StatusCode::from_u16(status).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR),
        [("content-type", "application/problem+json")],
        Json(body),
    )
        .into_response()
}
