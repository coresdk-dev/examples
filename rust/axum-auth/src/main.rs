/// CoreSDK — Axum JWT auth + Rego policy as Tower middleware.
///
/// Run:  cargo run
/// Try:  curl -H "Authorization: Bearer <token>" http://localhost:3000/me
use axum::{extract::Extension, routing::get, Json, Router};
use coresdk_engine::{CoreEngine, EngineConfig};
use coresdk_engine::axum::{auth_layer, policy_layer, CurrentUser};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let engine = CoreEngine::new(EngineConfig::from_env()?).await?;

    let app = Router::new()
        .route("/me", get(me))
        .route("/admin", get(admin))
        .layer(auth_layer(engine.auth()))        // validates JWT on every request
        .layer(Extension(engine));

    let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await?;
    println!("listening on :3000");
    axum::serve(listener, app).await?;
    Ok(())
}

async fn me(Extension(user): Extension<CurrentUser>) -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "user_id": user.sub,
        "tenant": user.tenant_id,
        "roles": user.roles,
    }))
}

// Requires "admin" role — 403 otherwise
#[coresdk_engine::require_role("admin")]
async fn admin(Extension(user): Extension<CurrentUser>) -> Json<serde_json::Value> {
    Json(serde_json::json!({ "message": format!("hello admin {}", user.sub) }))
}
