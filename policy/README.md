# CoreSDK Policy Bundle — Rego Examples

This directory contains a Rego policy bundle demonstrating RBAC and ABAC patterns
for use with CoreSDK's policy engine (backed by [regorus](https://github.com/microsoft/regorus)).

## What is Rego?

Rego is the policy language used by the Open Policy Agent (OPA) project.
CoreSDK embeds regorus — a pure-Rust Rego evaluator — so you get policy enforcement
without running a separate OPA process or depending on a C/Go runtime.

Policies are structured as packages (e.g. `package authz`) with named rules.
CoreSDK evaluates a single boolean rule per request (default: `data.authz.allow`).

## Deploying via the control plane (recommended for production)

The control plane distributes policies to all connected sidecars. The sidecar
hot-reloads the policy bundle on each sync tick (default 30s) without restarting.

```bash
# Start the control plane (if not already running)
docker run -d --name coresdk-cp \
  -e CORESDK_CONTROL_PLANE_API_KEY=dev-token \
  -p 8080:8080 \
  ghcr.io/coresdk-dev/control-plane:latest

# Upload this policy bundle
BUNDLE_B64=$(base64 -i policy/authz.rego)
curl -s -X PUT http://localhost:8080/api/v1/policies \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -d "{\"bundle_b64\": \"$BUNDLE_B64\"}"
```

To combine multiple `.rego` files into one bundle upload:

```bash
cat policy/authz.rego policy/tenant_isolation.rego | base64 | tr -d '\n' > /tmp/bundle.b64
curl -s -X PUT http://localhost:8080/api/v1/policies \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -d "{\"bundle_b64\": \"$(cat /tmp/bundle.b64)\"}"
```

Watch for the sidecar log line confirming the reload:

```
Policy bundle hot-reloaded from control plane
```

## Loading a bundle via coresdk.toml (local dev shortcut)

For local development you can point the sidecar directly at a local directory
and skip the control plane:

```toml
[policy]
bundle_dir   = "../../policy"   # path to this directory
default_rule = "data.authz.allow"
```

All `.rego` files in `bundle_dir` are loaded at sidecar startup and hot-reloaded
on change (via `ArcSwap` + inotify). No restart required.

## Input fields

Every policy evaluation receives an `input` object with these fields:

| Field              | Type            | Description                                              |
|--------------------|-----------------|----------------------------------------------------------|
| `subject`          | `string`        | Authenticated user identifier (JWT `sub` claim)          |
| `action`           | `string`        | Operation being performed: `read`, `write`, `create`, `update`, `delete` |
| `resource`         | `string`        | Resource path or identifier, e.g. `documents/doc-1`     |
| `tenant_id`        | `string`        | Tenant the request was authenticated into                |
| `context.roles`    | `array[string]` | Roles from JWT claims, e.g. `["editor", "viewer"]`       |
| `resource_owner`   | `string`        | (ABAC) Subject who owns the resource — set by your app   |
| `resource_tenant`  | `string`        | (ABAC) Tenant the resource belongs to                    |

For tenant isolation checks (`package tenant`):

| Field               | Type     | Description                      |
|---------------------|----------|----------------------------------|
| `jwt_tenant`        | `string` | Tenant from the JWT claim        |
| `requested_tenant`  | `string` | Tenant referenced in the request |

## RBAC pattern (authz.rego)

Role-based rules grant access by membership in a role set:

```python
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
```

## ABAC pattern (authz.rego)

Attribute-based rules grant access based on resource attributes, not just roles:

```python
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
```

The fastapi-app example (`python/fastapi-app/main.py`) demonstrates ABAC in the
`GET /documents/{doc_id}` route — it passes `resource_owner` and `resource_tenant`
from the in-memory document store into `evaluate_policy`, so the Rego owner rule
fires without any role requirement.

## Testing policies with the CoreSDK CLI

```bash
# Evaluate a rule against a JSON input file
coresdk policy eval data.authz.allow --input input.json --bundle-dir .

# Run all tests in *_test.rego files
coresdk policy test --bundle-dir .

# Watch for changes and re-run tests
coresdk policy test --bundle-dir . --watch
```

Example `input.json`:

```json
{
  "subject": "alice",
  "action": "read",
  "resource": "documents/doc-1",
  "tenant_id": "acme-corp",
  "resource_owner": "alice",
  "resource_tenant": "acme-corp",
  "context": { "roles": ["viewer"] }
}
```

Expected result: `true` — alice is the resource owner, so the ABAC owner rule fires
regardless of her `viewer` role.
