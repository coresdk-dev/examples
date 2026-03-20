/**
 * CoreSDK — Next.js Edge middleware (runs on Vercel/Cloudflare too).
 *
 * Drop this file at the root of your Next.js project.
 * All /api/* and /dashboard/* routes require a valid JWT automatically.
 */
import { withCoreSDKAuth } from "@coresdk/sdk/next";

export default withCoreSDKAuth({
  // Routes that don't require auth
  publicPaths: ["/", "/login", "/signup", "/api/health"],
});

export const config = {
  matcher: ["/api/:path*", "/dashboard/:path*"],
};
