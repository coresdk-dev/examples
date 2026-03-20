/**
 * CoreSDK — Express JWT auth in one line.
 *
 * Install:  npm install @coresdk/sdk express
 * Run:      npx ts-node index.ts
 * Try:      curl -H "Authorization: Bearer <token>" http://localhost:3000/me
 */
import express from "express";
import { requireAuth, requireRole, currentUser } from "@coresdk/sdk/express";

const app = express();

// All routes below require a valid JWT
app.use(requireAuth());

app.get("/me", (req, res) => {
  const user = currentUser(req);
  res.json({ userId: user.sub, tenant: user.tenantId, roles: user.roles });
});

app.get("/admin", requireRole("admin"), (req, res) => {
  res.json({ message: "welcome admin" });
});

app.listen(3000, () => console.log("listening on :3000"));
