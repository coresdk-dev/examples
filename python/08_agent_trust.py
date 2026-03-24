"""Example: Agent-to-agent JWT delegation — mint a child token from a parent."""

import os
from coresdk import SDK

sdk = SDK.from_env()

parent_token = os.getenv("PARENT_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.parent")

print("=== Agent Trust Example ===\n")
print(f"Parent token: {parent_token[:40]}...")

# Mint a delegated token for the data-service with read scope
agent = sdk.mint_agent_token(
    parent_token=parent_token,
    target_service="data-service",
    scopes=["read"],
    ttl_seconds=120,
)

print("\nMinted agent token:")
print(f"  Token (first 40): {agent.token[:40]}...")
print(f"  Expires in:       {agent.expires_in_seconds}s")
print(f"  Delegation chain: {' -> '.join(agent.agent_chain)}")

# Now pass agent.token to the downstream service
# The downstream service validates it as a normal JWT
print("\nPass agent.token to data-service as Bearer token.")
print("Set CORESDK_AGENT_SIGNING_SECRET for persistent key across restarts.")
