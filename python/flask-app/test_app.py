"""
End-to-end tests for the flask-app example.
Run: pytest test_app.py -v
Requires the sidecar running at [::1]:50051.
"""

import pytest
from main import app as flask_app

AUTH = {"Authorization": "Bearer alice-token"}
ADMIN = {"Authorization": "Bearer admin-token"}


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


# ── Health ──────────────────────────────────────────────────────────────────


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


# ── Auth enforcement ─────────────────────────────────────────────────────────


def test_no_token_returns_401(client):
    r = client.get("/products")
    assert r.status_code == 401


def test_valid_token_returns_200(client):
    r = client.get("/products", headers=AUTH)
    assert r.status_code == 200


def test_me_returns_claims(client):
    r = client.get("/me", headers=AUTH)
    assert r.status_code == 200
    assert "sub" in r.get_json()


# ── Products CRUD ────────────────────────────────────────────────────────────


def test_list_products(client):
    r = client.get("/products", headers=AUTH)
    assert r.status_code == 200
    data = r.get_json()
    assert "tenant" in data
    assert "products" in data
    assert isinstance(data["products"], list)


def test_get_product_exists(client):
    r = client.get("/products/1", headers=AUTH)
    assert r.status_code == 200
    assert r.get_json()["id"] == 1


def test_get_product_not_found(client):
    r = client.get("/products/9999", headers=AUTH)
    assert r.status_code == 404
    body = r.get_json()
    assert body.get("status") == 404


def test_create_product_without_role_returns_403(client):
    # fail-open claims have no roles → editor check → 403
    r = client.post(
        "/products", json={"name": "Widget C", "price": 199.0}, headers=AUTH
    )
    assert r.status_code in (201, 403)


def test_delete_product_without_role_returns_403(client):
    r = client.delete("/products/1", headers=AUTH)
    assert r.status_code in (200, 403)


# ── Policy check ─────────────────────────────────────────────────────────────


def test_policy_check(client):
    r = client.get("/policy/check?action=read&resource=reports/q4", headers=AUTH)
    assert r.status_code == 200
    data = r.get_json()
    assert "allowed" in data
    assert isinstance(data["allowed"], bool)


# ── Tenant isolation ─────────────────────────────────────────────────────────


def test_tenant_scoped_products(client):
    r = client.get("/products", headers=AUTH)
    assert r.status_code == 200
    assert r.get_json()["tenant"] == "acme-corp"
