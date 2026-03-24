# Egress allowlist policy — controls which outbound URLs are allowed.
# Deploy to: PUT /api/v1/policies with this file in the bundle.
#
# Default (fail-open): all external URLs allowed (RFC-1918 always blocked in engine).
# To enable allowlist mode: set "default allow = false" and add domain rules.

package coresdk.egress

# Default: fail-open — allow all external URLs.
# RFC-1918 / loopback / link-local are ALWAYS blocked regardless of this policy.
default allow = true

# To switch to allowlist mode, uncomment and customize:
# default allow = false
#
# allow {
#     # Allow requests to your own API
#     contains(input.host, "api.mycompany.com")
# }
#
# allow {
#     # Allow npm/pip registries
#     input.host == "registry.npmjs.org"
# }
#
# allow {
#     # Allow by URL prefix
#     startswith(input.url, "https://api.stripe.com/")
# }
