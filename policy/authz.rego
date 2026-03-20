# CoreSDK — Example Rego Policy Bundle
# Demonstrates RBAC + ABAC patterns
# Load via: bundle_dir = "../../policy" in coresdk.toml

package authz

import rego.v1

# ── RBAC: role-based allow ────────────────────────────────────────────────────

# Default deny
default allow := false

# Admin can do anything
allow if {
    "admin" in input.context.roles
}

# Editor can read and write, but not delete
allow if {
    "editor" in input.context.roles
    input.action in {"read", "write", "create", "update"}
}

# Viewer can only read
allow if {
    "viewer" in input.context.roles
    input.action == "read"
}

# ── ABAC: attribute-based rules ───────────────────────────────────────────────

# Resource owner can always read/update their own resource
allow if {
    input.action in {"read", "update"}
    input.resource_owner == input.subject
}

# Tenant isolation: subject must belong to the same tenant as the resource
allow if {
    input.tenant_id == input.resource_tenant
    "editor" in input.context.roles
}

# Time-based access: only allow writes during business hours (UTC)
allow if {
    input.action in {"create", "update", "delete"}
    hour := time.clock(time.now_ns())[0]
    hour >= 8
    hour < 20
}

# ── Helper rules ──────────────────────────────────────────────────────────────

# Deny reason for audit log
deny_reason := reason if {
    not allow
    "admin" not in input.context.roles
    reason := sprintf("subject=%s lacks permission: action=%s resource=%s roles=%v",
        [input.subject, input.action, input.resource, input.context.roles])
}

deny_reason := "admin required" if {
    not allow
    "admin" not in input.context.roles
}
