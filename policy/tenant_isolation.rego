package tenant

import rego.v1

# Enforce that the JWT tenant_id matches the requested tenant
default isolated := false

isolated if {
    input.jwt_tenant == input.requested_tenant
}

violation[msg] if {
    not isolated
    msg := sprintf("tenant mismatch: token belongs to %s, request targets %s",
        [input.jwt_tenant, input.requested_tenant])
}
