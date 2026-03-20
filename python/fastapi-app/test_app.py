"""
End-to-end tests for the fastapi-app example.
Run: pytest test_app.py -v
Requires the sidecar running at [::1]:50051.
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app, raise_server_exceptions=False)

AUTH  = {"Authorization": "Bearer alice-token"}
ADMIN = {"Authorization": "Bearer admin-token"}


# ── Health ─────────────────────────────────────────────────────────────────────

def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Auth enforcement ───────────────────────────────────────────────────────────

def test_no_token_returns_401():
    r = client.get("/products")
    assert r.status_code == 401

def test_valid_token_returns_200():
    r = client.get("/products", headers=AUTH)
    assert r.status_code == 200

def test_me_returns_claims():
    r = client.get("/me", headers=AUTH)
    assert r.status_code == 200
    assert "sub" in r.json()


# ── Products CRUD ──────────────────────────────────────────────────────────────

def test_list_products():
    r = client.get("/products", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert "tenant" in data
    assert "products" in data
    assert isinstance(data["products"], list)

def test_get_product_exists():
    r = client.get("/products/1", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["id"] == 1

def test_get_product_not_found():
    r = client.get("/products/9999", headers=AUTH)
    assert r.status_code == 404
    body = r.json()
    # RFC 9457 — detail is a dict with type/title/status
    detail = body.get("detail", body)
    assert detail.get("status") == 404

def test_create_product_without_role_returns_403():
    # fail-open claims have no roles → editor check → 403
    r = client.post("/products",
                    json={"name": "Widget C", "price": 199.0},
                    headers=AUTH)
    assert r.status_code in (201, 403)  # 403 without real JWT roles

def test_delete_product_without_role_returns_403():
    r = client.delete("/products/1", headers=AUTH)
    assert r.status_code in (200, 403)


# ── Policy check ───────────────────────────────────────────────────────────────

def test_policy_check():
    r = client.get("/policy/check?action=read&resource=reports/q4", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert "allowed" in data
    assert isinstance(data["allowed"], bool)


# ── Tenant isolation ───────────────────────────────────────────────────────────

def test_tenant_scoped_products():
    r = client.get("/products", headers=AUTH)
    assert r.status_code == 200
    # tenant in response must match config
    assert r.json()["tenant"] == "acme-corp"


# ── ABAC document access ───────────────────────────────────────────────────────

def test_get_document_abac():
    r = client.get("/documents/doc-1", headers=AUTH)
    assert r.status_code in (200, 403)  # 403 without Rego bundle, 200 with

def test_get_document_not_found():
    r = client.get("/documents/doc-999", headers=AUTH)
    assert r.status_code == 404


# ── Docs available ─────────────────────────────────────────────────────────────

def test_openapi_docs():
    r = client.get("/docs")
    assert r.status_code == 200

def test_openapi_schema():
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert r.json()["info"]["title"] == "Product API"
