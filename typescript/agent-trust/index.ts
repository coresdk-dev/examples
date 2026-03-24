/**
 * Example: Agent-to-agent JWT delegation + SSRF-safe fetch.
 */
import { SDK } from '@coresdk/sdk';
import { createCoreFetch } from '@coresdk/sdk/egress';

const sdk = SDK.fromEnv();

async function main() {
  const parentToken = process.env.PARENT_TOKEN ?? 'test-parent-token';

  console.log('=== Agent Trust + Egress Example ===\n');

  // Mint a delegated token
  const agent = await sdk.mintAgentToken(parentToken, 'analytics-service', ['read'], 120);
  console.log(`Minted agent token (first 40): ${agent.token.slice(0, 40)}...`);
  console.log(`Expires in: ${agent.expiresInSeconds}s`);
  console.log(`Chain: ${agent.agentChain.join(' -> ')}`);

  // SSRF-safe fetch
  console.log('\nSSRF-safe fetch:');
  const safeFetch = createCoreFetch(sdk);

  try {
    await safeFetch('http://169.254.169.254/latest/meta-data/');
  } catch (err) {
    console.log(`  Blocked metadata endpoint: ${err}`);
  }

  const decision = await sdk.checkEgress('https://api.example.com/data');
  console.log(`  External API: ${decision.allowed ? 'allowed' : 'blocked'}`);
}

main().catch(console.error);
