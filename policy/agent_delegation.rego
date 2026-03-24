# Agent delegation policy — controls which parent agents can mint child tokens.
# Deploy to: PUT /api/v1/policies with this file in the bundle.
#
# To enable allowlist mode: set "default allow = false" and add explicit rules.
# Default (fail-open): all delegation is allowed.

package coresdk.agent_delegation

# Default: fail-open — allow all delegation.
# Change to `false` to require explicit allow rules.
default allow = true

# Example: only allow delegation to specific services
# allow {
#     input.target_service == "data-service"
#     input.scopes[_] == "read"
# }

# Example: allow delegation if parent has the agent_delegator role
# allow {
#     input.parent_claims.roles[_] == "agent_delegator"
# }
