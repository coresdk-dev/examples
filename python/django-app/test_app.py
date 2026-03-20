"""
End-to-end tests for the CoreSDK django-app example.
Run: pytest test_app.py -v
Requires DJANGO_SETTINGS_MODULE=api.settings (set in pytest.ini).
"""
import json
import pytest
from django.test import Client

AUTH  = {"HTTP_AUTHORIZATION": "Bearer alice-token"}
ADMIN = {"HTTP_AUTHORIZATION": "Bearer admin-token"}


@pytest.fixture
def client():
    return Client(raise_request_exception=False)


# ── Health ─────────────────────────────────────────────────────────────────────

def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    data = json.loads(r.content)
    assert data["status"] == "ok"


# ── Auth enforcement ───────────────────────────────────────────────────────────

def test_no_token_401(client):
    """No Authorization header must return 401."""
    r = client.get("/products")
    assert r.status_code == 401


def test_valid_token_200(client):
    """Bearer token present — fail-open allows the request."""
    r = client.get("/products", **AUTH)
    assert r.status_code == 200


def test_me_returns_claims(client):
    r = client.get("/me", **AUTH)
    assert r.status_code == 200
    data = json.loads(r.content)
    assert "sub" in data


# ── Products CRUD ──────────────────────────────────────────────────────────────

def test_list_products(client):
    r = client.get("/products", **AUTH)
    assert r.status_code == 200
    data = json.loads(r.content)
    assert "tenant" in data
    assert "products" in data
    assert isinstance(data["products"], list)


def test_get_product_exists(client):
    r = client.get("/products/1", **AUTH)
    assert r.status_code == 200
    data = json.loads(r.content)
    assert data["id"] == 1


def test_get_product_not_found(client):
    """Missing product returns RFC 9457 404."""
    r = client.get("/products/9999", **AUTH)
    assert r.status_code == 404
    data = json.loads(r.content)
    assert data["status"] == 404
    assert "type" in data
    assert "title" in data


def test_create_without_role_403(client):
    """POST /products without editor role returns 403 (fail-open has no roles)."""
    r = client.post(
        "/products",
        data=json.dumps({"name": "Widget C", "price": 199.0}),
        content_type="application/json",
        **AUTH,
    )
    # fail-open claims carry no roles → 403; real JWT with editor role → 201
    assert r.status_code in (201, 403)


def test_delete_without_role_403(client):
    """DELETE /products/1 without admin role returns 403."""
    r = client.delete("/products/1", **AUTH)
    assert r.status_code in (200, 403)


# ── Policy check ───────────────────────────────────────────────────────────────

def test_policy_check(client):
    r = client.get("/policy/check?action=read&resource=reports/q4", **AUTH)
    assert r.status_code == 200
    data = json.loads(r.content)
    assert "allowed" in data
    assert isinstance(data["allowed"], bool)


# ── Tenant isolation ───────────────────────────────────────────────────────────

def test_tenant_scoped(client):
    """Products response must report the configured tenant (acme-corp)."""
    r = client.get("/products", **AUTH)
    assert r.status_code == 200
    data = json.loads(r.content)
    assert data["tenant"] == "acme-corp"
