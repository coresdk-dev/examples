# CoreSDK — Policy unit tests
# Run with: opa test policy/ -v
# Or via the CoreSDK CLI: coresdk policy test --bundle-dir policy/

package authz_test

import data.authz

# ── Viewer ────────────────────────────────────────────────────────────────────

test_viewer_can_read if {
    authz.allow with input as {
        "subject": "alice",
        "action": "read",
        "resource": "doc-1",
        "tenant_id": "acme",
        "context": {"roles": ["viewer"]},
    }
}

test_viewer_cannot_write if {
    not authz.allow with input as {
        "subject": "alice",
        "action": "write",
        "resource": "doc-1",
        "tenant_id": "acme",
        "context": {"roles": ["viewer"]},
    }
}

test_viewer_cannot_delete if {
    not authz.allow with input as {
        "subject": "alice",
        "action": "delete",
        "resource": "doc-1",
        "tenant_id": "acme",
        "context": {"roles": ["viewer"]},
    }
}

# ── Editor ────────────────────────────────────────────────────────────────────

test_editor_can_read if {
    authz.allow with input as {
        "subject": "bob",
        "action": "read",
        "resource": "doc-1",
        "tenant_id": "acme",
        "context": {"roles": ["editor"]},
    }
}

test_editor_can_write if {
    authz.allow with input as {
        "subject": "bob",
        "action": "write",
        "resource": "doc-1",
        "tenant_id": "acme",
        "context": {"roles": ["editor"]},
    }
}

test_editor_cannot_delete if {
    not authz.allow with input as {
        "subject": "bob",
        "action": "delete",
        "resource": "doc-1",
        "tenant_id": "acme",
        "context": {"roles": ["editor"]},
    }
}

# ── Admin ─────────────────────────────────────────────────────────────────────

test_admin_can_delete if {
    authz.allow with input as {
        "subject": "carol",
        "action": "delete",
        "resource": "doc-1",
        "tenant_id": "acme",
        "context": {"roles": ["admin"]},
    }
}

test_admin_can_read if {
    authz.allow with input as {
        "subject": "carol",
        "action": "read",
        "resource": "doc-1",
        "tenant_id": "acme",
        "context": {"roles": ["admin"]},
    }
}

# ── No roles ──────────────────────────────────────────────────────────────────

test_no_roles_denied if {
    not authz.allow with input as {
        "subject": "hacker",
        "action": "read",
        "resource": "doc-1",
        "tenant_id": "acme",
        "context": {"roles": []},
    }
}

# ── ABAC: resource owner ──────────────────────────────────────────────────────

test_owner_can_update_own_resource if {
    authz.allow with input as {
        "subject": "alice",
        "action": "update",
        "resource": "doc-1",
        "resource_owner": "alice",
        "tenant_id": "acme",
        "context": {"roles": ["viewer"]},
    }
}

test_non_owner_cannot_update if {
    not authz.allow with input as {
        "subject": "bob",
        "action": "update",
        "resource": "doc-1",
        "resource_owner": "alice",
        "tenant_id": "acme",
        "context": {"roles": ["viewer"]},
    }
}
