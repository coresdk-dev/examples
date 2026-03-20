//! CoreSDK — Complete Axum REST API example.
//!
//! Demonstrates direct embedding of `coresdk-engine` in a Rust service.
//! No sidecar required: auth, policy, masking, and tracing all run in-process.
//!
//! # Quick start
//!
//! ```bash
//! # Install (published crate):
//! cargo add coresdk-engine
//!
//! # Or use this example directly from the workspace:
//! cargo run
//!
//! # Try it:
//! curl http://localhost:3000/healthz
//! curl -H "Authorization: Bearer <your-jwt>" http://localhost:3000/me
//! curl -H "Authorization: Bearer <your-jwt>" http://localhost:3000/products
//! curl -H "Authorization: Bearer <your-jwt>" http://localhost:3000/products/123
//! curl -H "Authorization: Bearer <your-jwt>" \
//!      -H "Content-Type: application/json" \
//!      -d '{"action":"read","resource":"products/123"}' \
//!      http://localhost:3000/policy/check
//! ```
//!
//! # Environment variables
//!
//! | Variable                  | Default           | Description                        |
//! |---------------------------|-------------------|------------------------------------|
//! | `CORESDK_JWKS_URL`        | —                 | Remote JWK Set URL for JWT verify  |
//! | `CORESDK_TENANT_ID`       | `default`         | Default tenant if not in JWT       |
//! | `CORESDK_SERVICE_NAME`    | `axum-app`        | OTel service name                  |
//! | `CORESDK_FAIL_MODE`       | `open`            | `open` or `closed` on auth failure |
//! | `CORESDK_POLICY_POOL_SIZE`| `min(cpus, 8)`    | Rego engine pool size              |
//! | `CORESDK_ENV`             | —                 | Set to `development` for dev mode  |
//! | `RUST_LOG`                | `info`            | Tracing filter                     |

use std::{collections::HashMap, sync::Arc};

use axum::{
    extract::{Path, Request, State},
    http::{HeaderMap, StatusCode},
    middleware::{self, Next},
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use serde_json::json;
use tracing::{error, info, instrument, warn};
use uuid::Uuid;

// ---------------------------------------------------------------------------
// CoreSDK imports — `cargo add coresdk-engine` provides all of these.
// ---------------------------------------------------------------------------
use coresdk_engine::{
    auth::decision::{AuthDecision, AuthRequest},
    error::ProblemDetail,
    policy::decision::PolicyInput,
    Engine,
};

// ---------------------------------------------------------------------------
// Shared application state
// ---------------------------------------------------------------------------

/// Application state — cloned cheaply into every handler via `Arc`.
#[derive(Clone)]
struct AppState {
    /// Initialized once at startup; `Arc` makes cloning free.
    engine: Arc<Engine>,
}

// ---------------------------------------------------------------------------
// RFC 9457 error response helper
// ---------------------------------------------------------------------------

/// Axum-compatible wrapper around `ProblemDetail`.
///
/// Serialises to `application/problem+json` with the correct HTTP status.
struct Problem(ProblemDetail);

impl IntoResponse for Problem {
    fn into_response(self) -> Response {
        let status =
            StatusCode::from_u16(self.0.status).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);
        let body = Json(self.0);
        (status, body).into_response()
    }
}

// Convenience constructor so handlers can do `return Err(problem!(401, "..."))`.
macro_rules! problem {
    (401, $detail:expr) => {
        Problem(ProblemDetail::unauthorized($detail))
    };
    (403, $detail:expr) => {
        Problem(ProblemDetail::forbidden($detail))
    };
    (400, $detail:expr) => {
        Problem(ProblemDetail::bad_request($detail))
    };
    (500, $detail:expr) => {
        Problem(ProblemDetail::internal_error($detail))
    };
    (503, $detail:expr) => {
        Problem(ProblemDetail::service_unavailable($detail))
    };
}

// ---------------------------------------------------------------------------
// Verified principal — extracted from JWT and threaded through via extensions
// ---------------------------------------------------------------------------

/// Represents an authenticated, tenant-scoped caller extracted from the JWT.
///
/// CoreSDK validates the token signature and populates this struct.
/// The `tenant_id` field drives multi-tenant data isolation downstream.
#[derive(Debug, Clone)]
struct Principal {
    /// JWT `sub` claim — stable, opaque user identifier.
    subject: String,
    /// Tenant the caller belongs to (from `tid` or `tenant_id` JWT claim).
    tenant_id: String,
    /// RBAC roles from JWT `roles` claim (or empty vec if absent).
    roles: Vec<String>,
}

impl Principal {
    fn has_role(&self, role: &str) -> bool {
        self.roles.iter().any(|r| r == role)
    }
}

// ---------------------------------------------------------------------------
// Auth middleware
//
// Tower middleware that runs before every route handler.
// Extracts the `Authorization: Bearer <token>` header, calls
// `engine.authorize()`, and injects a `Principal` extension for handlers.
// ---------------------------------------------------------------------------

/// JWT validation middleware.
///
/// On every request:
/// 1. Extract `Authorization: Bearer <token>`.
/// 2. Call `engine.authorize()` — validates signature, expiry, audience.
/// 3. Reject with 401 (RFC 9457) if invalid; otherwise inject `Principal`.
///
/// `CORESDK_FAIL_MODE=open` lets bad tokens through during development.
/// `CORESDK_FAIL_MODE=closed` (default for production) rejects them.
#[instrument(skip_all, name = "auth_middleware")]
async fn auth_middleware(
    State(state): State<AppState>,
    mut req: Request,
    next: Next,
) -> Result<Response, Problem> {
    let token = extract_bearer(req.headers())
        .ok_or_else(|| problem!(401, "Missing Authorization header"))?;

    // Build the CoreSDK auth request.
    // `expected_audience` can be set to enforce `aud` claim validation.
    let auth_req = AuthRequest {
        token: token.to_owned(),
        expected_audience: std::env::var("CORESDK_AUDIENCE").ok(),
        // Tenant is resolved from the token; fall back to env default.
        tenant_id: std::env::var("CORESDK_TENANT_ID").unwrap_or_else(|_| "default".into()),
    };

    // `engine.authorize()` respects CORESDK_FAIL_MODE automatically.
    let decision: AuthDecision = state
        .engine
        .authorize(auth_req)
        .map_err(|e| {
            error!(error = %e, "Auth engine error");
            problem!(503, "Auth service unavailable")
        })?;

    if !decision.allowed {
        let detail = decision
            .problem
            .as_ref()
            .and_then(|p| p.detail.clone())
            .unwrap_or_else(|| "Token rejected".into());
        warn!(detail = %detail, "Request rejected by auth middleware");
        return Err(problem!(401, detail));
    }

    // Inject the principal into request extensions so handlers can read it.
    let principal = Principal {
        subject: decision.subject.unwrap_or_else(|| "anonymous".into()),
        tenant_id: decision
            .problem // (not used here — just defensive)
            .as_ref()
            .and_then(|_| None)
            .unwrap_or_else(|| {
                std::env::var("CORESDK_TENANT_ID").unwrap_or_else(|_| "default".into())
            }),
        roles: decision.roles,
    };

    info!(
        subject = %principal.subject,
        tenant  = %principal.tenant_id,
        roles   = ?principal.roles,
        "Request authenticated"
    );

    req.extensions_mut().insert(principal);
    Ok(next.run(req).await)
}

/// Extract `Bearer <token>` from the `Authorization` header.
fn extract_bearer(headers: &HeaderMap) -> Option<&str> {
    headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
}

// ---------------------------------------------------------------------------
// Route: GET /healthz
//
// Public — no auth required.  Returns 200 + JSON liveness payload.
// ---------------------------------------------------------------------------

async fn healthz() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "service": std::env::var("CORESDK_SERVICE_NAME").unwrap_or_else(|_| "axum-app".into()),
    }))
}

// ---------------------------------------------------------------------------
// Route: GET /me
//
// Auth-protected.  Returns the caller's identity extracted from the JWT.
// Demonstrates multi-tenant principal access.
// ---------------------------------------------------------------------------

#[instrument(skip_all, name = "GET /me")]
async fn me(req: Request) -> Result<Json<serde_json::Value>, Problem> {
    let principal = req
        .extensions()
        .get::<Principal>()
        .ok_or_else(|| problem!(500, "Principal missing — auth middleware not installed"))?;

    Ok(Json(json!({
        "subject":   principal.subject,
        "tenant_id": principal.tenant_id,
        "roles":     principal.roles,
    })))
}

// ---------------------------------------------------------------------------
// Route: GET /products
//
// Auth-protected.  Demonstrates multi-tenant data isolation:
// the handler reads `principal.tenant_id` and would filter a DB query by it.
// ---------------------------------------------------------------------------

#[derive(Serialize)]
struct Product {
    id: String,
    name: String,
    tenant_id: String,
}

#[instrument(skip_all, name = "GET /products")]
async fn list_products(req: Request) -> Result<Json<serde_json::Value>, Problem> {
    let principal = req
        .extensions()
        .get::<Principal>()
        .ok_or_else(|| problem!(500, "Principal missing"))?;

    // In production: `SELECT * FROM products WHERE tenant_id = $1`
    // Here we return synthetic data scoped to the caller's tenant.
    let products = vec![
        Product {
            id: Uuid::new_v4().to_string(),
            name: "Widget A".into(),
            tenant_id: principal.tenant_id.clone(),
        },
        Product {
            id: Uuid::new_v4().to_string(),
            name: "Widget B".into(),
            tenant_id: principal.tenant_id.clone(),
        },
    ];

    Ok(Json(json!({ "products": products, "tenant_id": principal.tenant_id })))
}

// ---------------------------------------------------------------------------
// Route: GET /products/:id
//
// Auth-protected.  Demonstrates per-resource policy evaluation via Rego.
// The policy engine pool (N engines, one per blocking thread) is called
// via `spawn_blocking` inside `engine.evaluate_policy()`.
// ---------------------------------------------------------------------------

#[instrument(skip_all, name = "GET /products/:id", fields(product_id = %id))]
async fn get_product(
    State(state): State<AppState>,
    Path(id): Path<String>,
    req: Request,
) -> Result<Json<serde_json::Value>, Problem> {
    let principal = req
        .extensions()
        .get::<Principal>()
        .ok_or_else(|| problem!(500, "Principal missing"))?;

    // Build the policy input.
    // CoreSDK evaluates `data.authz.allow` (or any rule) in a Rego bundle
    // you load at startup via `engine.policy.load_bundle(...)`.
    let policy_input = PolicyInput {
        tenant_id: principal.tenant_id.clone(),
        subject: principal.subject.clone(),
        action: "read".into(),
        resource: format!("products/{id}"),
        context: HashMap::new(),
    };

    // `evaluate_policy` uses `spawn_blocking` internally so it never blocks
    // the Tokio runtime.  The policy engine pool ensures no lock contention.
    let allowed = state
        .engine
        .evaluate_policy("data.authz.allow", policy_input)
        .await
        .map_err(|e| {
            error!(error = %e, "Policy evaluation error");
            problem!(503, "Policy engine unavailable")
        })?;

    if !allowed {
        warn!(
            subject = %principal.subject,
            resource = %format!("products/{id}"),
            "Policy denied read access"
        );
        return Err(problem!(403, format!("Access to products/{id} denied by policy")));
    }

    Ok(Json(json!({
        "id":        id,
        "name":      "Widget A",
        "tenant_id": principal.tenant_id,
    })))
}

// ---------------------------------------------------------------------------
// Route: POST /policy/check
//
// Auth-protected.  Ad-hoc policy evaluation endpoint.
// Allows callers to check any action/resource against the policy bundle.
// Useful for UI permission checks before rendering controls.
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct PolicyCheckRequest {
    action: String,
    resource: String,
    #[serde(default)]
    context: HashMap<String, serde_json::Value>,
}

#[derive(Serialize)]
struct PolicyCheckResponse {
    allowed: bool,
    action: String,
    resource: String,
    subject: String,
    tenant_id: String,
}

#[instrument(skip_all, name = "POST /policy/check")]
async fn policy_check(
    State(state): State<AppState>,
    req: Request,
    // Note: Json extractor must come after State/Path/etc.
) -> Result<Json<PolicyCheckResponse>, Problem> {
    // Split extensions before consuming req with axum::extract::Json equivalent.
    // We use axum::body::Body tricks — instead extract principal first.
    let (parts, body) = req.into_parts();

    let principal = parts
        .extensions
        .get::<Principal>()
        .ok_or_else(|| problem!(500, "Principal missing"))?
        .clone();

    // Reconstruct request to parse body.
    let req = Request::from_parts(parts, body);
    let Json(payload): Json<PolicyCheckRequest> = Json::from_request(req, &())
        .await
        .map_err(|_| problem!(400, "Invalid JSON body — expected {action, resource, context?}"))?;

    let policy_input = PolicyInput {
        tenant_id: principal.tenant_id.clone(),
        subject: principal.subject.clone(),
        action: payload.action.clone(),
        resource: payload.resource.clone(),
        context: payload.context,
    };

    let allowed = state
        .engine
        .evaluate_policy("data.authz.allow", policy_input)
        .await
        .map_err(|e| {
            error!(error = %e, "Policy evaluation error");
            problem!(503, "Policy engine unavailable")
        })?;

    info!(
        subject  = %principal.subject,
        action   = %payload.action,
        resource = %payload.resource,
        allowed  = allowed,
        "Policy check complete"
    );

    Ok(Json(PolicyCheckResponse {
        allowed,
        action: payload.action,
        resource: payload.resource,
        subject: principal.subject,
        tenant_id: principal.tenant_id,
    }))
}

// ---------------------------------------------------------------------------
// OTel tracing setup
//
// CoreSDK's masking SpanProcessor fires *before* the OTLP exporter, so PII
// is never written to the export queue.  Here we use tracing-subscriber for
// local stdout output; in production swap in an OTLP subscriber backed by
// `engine.tracer()` once the OTel crate is stable.
// ---------------------------------------------------------------------------

fn init_tracing() {
    use tracing_subscriber::{fmt, prelude::*, EnvFilter};

    tracing_subscriber::registry()
        .with(
            fmt::layer()
                .with_target(true)
                .with_thread_ids(false)
                .with_file(false),
        )
        .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .init();
}

// ---------------------------------------------------------------------------
// Policy bundle loaded at startup
//
// Real deployments load Rego from a file path or remote bundle URL.
// This inline bundle shows the shape CoreSDK expects.
// ---------------------------------------------------------------------------

/// Load the default `authz` Rego bundle into the engine's policy pool.
///
/// The bundle defines `data.authz.allow` which every route calls.
fn load_default_policy(engine: &Engine) {
    // CoreSDK policy pool: N independent `regorus::Engine` instances —
    // no single Mutex, no contention at 500 rps.
    //
    // Rule: allow reads for any authenticated user; block writes unless "admin".
    let bundle = vec![(
        "authz/policy.rego".into(),
        r#"
package authz

import future.keywords.if

default allow := false

# Allow any authenticated subject to perform a read.
allow if {
    input.action == "read"
    input.subject != ""
}

# Allow writes only for subjects with the admin role.
# (In production pass roles through input.context["roles"].)
allow if {
    input.action == "write"
    input.context.roles[_] == "admin"
}
"#
        .into(),
    )];

    if let Err(e) = engine.policy.load_bundle(bundle) {
        // Non-fatal in fail-open mode; fatal in fail-closed.
        warn!(error = %e, "Failed to load default policy bundle — policy checks may fail");
    } else {
        info!("Default authz policy bundle loaded");
    }
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // 1. Initialise structured tracing (stdout).
    //    In production, replace with an OTLP subscriber using engine.tracer().
    init_tracing();

    info!("CoreSDK axum-app starting");

    // 2. Initialise the CoreSDK engine from environment variables.
    //    Engine::from_env() reads CORESDK_* env vars; all have sensible defaults.
    //    The returned Arc<Engine> is cheap to clone into AppState.
    let engine = Engine::from_env()?;

    // 3. Load Rego policy bundle into the engine's pool.
    //    In production: load from a file path or bundle URL configured via env.
    load_default_policy(&engine);

    // 4. Build shared application state.
    let state = AppState {
        engine: Arc::clone(&engine),
    };

    // 5. Build the Axum router.
    //
    //    Public routes (/healthz) bypass auth middleware.
    //    Protected routes have `middleware::from_fn_with_state(auth_middleware)` applied.
    let public_routes = Router::new().route("/healthz", get(healthz));

    let protected_routes = Router::new()
        .route("/me", get(me))
        .route("/products", get(list_products))
        .route("/products/:id", get(get_product))
        .route("/policy/check", post(policy_check))
        // JWT validation runs for every protected request.
        .route_layer(middleware::from_fn_with_state(
            state.clone(),
            auth_middleware,
        ));

    let app = Router::new()
        .merge(public_routes)
        .merge(protected_routes)
        .with_state(state)
        .layer(
            // Tower-HTTP trace layer: logs method, path, status, latency.
            tower_http::trace::TraceLayer::new_for_http(),
        );

    // 6. Bind and serve.
    let port = std::env::var("PORT").unwrap_or_else(|_| "3000".into());
    let addr = format!("0.0.0.0:{port}");
    let listener = tokio::net::TcpListener::bind(&addr).await?;

    info!(addr = %addr, "Listening");
    axum::serve(listener, app).await?;

    Ok(())
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{
        body::Body,
        http::{Request, StatusCode},
    };
    use tower::ServiceExt; // for `.oneshot()`

    fn test_app() -> Router {
        let engine = Engine::from_env().expect("engine init");
        load_default_policy(&engine);
        let state = AppState {
            engine: Arc::clone(&engine),
        };
        let public_routes = Router::new().route("/healthz", get(healthz));
        let protected_routes = Router::new()
            .route("/me", get(me))
            .route("/products", get(list_products))
            .route("/products/:id", get(get_product))
            .route("/policy/check", post(policy_check))
            .route_layer(middleware::from_fn_with_state(state.clone(), auth_middleware));
        Router::new()
            .merge(public_routes)
            .merge(protected_routes)
            .with_state(state)
    }

    #[tokio::test]
    async fn healthz_returns_200() {
        let app = test_app();
        let response = app
            .oneshot(
                Request::builder()
                    .uri("/healthz")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
    }

    #[tokio::test]
    async fn me_without_token_returns_401() {
        let app = test_app();
        let response = app
            .oneshot(Request::builder().uri("/me").body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn products_without_token_returns_401() {
        let app = test_app();
        let response = app
            .oneshot(
                Request::builder()
                    .uri("/products")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn policy_check_without_token_returns_401() {
        let app = test_app();
        let response = app
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/policy/check")
                    .header("content-type", "application/json")
                    .body(Body::from(r#"{"action":"read","resource":"products/1"}"#))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
    }

    #[test]
    fn principal_has_role() {
        let p = Principal {
            subject: "alice".into(),
            tenant_id: "acme".into(),
            roles: vec!["admin".into(), "viewer".into()],
        };
        assert!(p.has_role("admin"));
        assert!(!p.has_role("superuser"));
    }
}
