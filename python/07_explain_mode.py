"""Example: Per-request explain mode — understand why a decision was made."""

import os
from coresdk import SDK

sdk = SDK.from_env()

# Use a test token (in real usage this comes from your auth system)
token = os.getenv("TEST_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test")

print("=== Explain Mode Example ===\n")

# Call explain_authorize instead of authorize to get a detailed breakdown
result = sdk.explain_authorize(token, action="read", resource="/orders")

print(f"Outcome:    {result.outcome}")
print(f"Request ID: {result.request_id}")
print(f"Latency:    {result.latency_ms:.1f}ms")

if result.auth:
    print("\nAuth details:")
    for k, v in result.auth.items():
        print(f"  {k}: {v}")

if result.policy:
    print("\nPolicy details:")
    for k, v in result.policy.items():
        print(f"  {k}: {v}")

# Also enable globally for all requests via environment variable:
# CORESDK_EXPLAIN=true

print("\nDone. Enable CORESDK_EXPLAIN=true to explain every request automatically.")
