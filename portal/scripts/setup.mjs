#!/usr/bin/env node
// One-click local setup for the Omni Loop Portal:
//   npm run setup
// Creates .env.local (with a fresh SESSION_SECRET) if missing, installs
// dependencies if needed, and prints next steps.

import { execSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const envExample = path.join(root, ".env.example");
const envLocal = path.join(root, ".env.local");

if (!fs.existsSync(envLocal)) {
  let env = fs.readFileSync(envExample, "utf8");
  env = env.replace(/^SESSION_SECRET=$/m, `SESSION_SECRET=${crypto.randomBytes(32).toString("hex")}`);
  fs.writeFileSync(envLocal, env);
  console.log("✓ Created .env.local with a fresh SESSION_SECRET");
} else {
  console.log("• .env.local already exists — leaving it untouched");
}

if (!fs.existsSync(path.join(root, "node_modules"))) {
  console.log("• Installing dependencies (this can take a minute)…");
  execSync("npm install", { cwd: root, stdio: "inherit" });
}

console.log(`
∞ Omni Loop Portal is ready.

  Start it:            npm run dev          → http://localhost:4280
  Production build:    npm run build && npm start

  Optional configuration in .env.local:
    OPENROUTER_API_KEY   enables real model inference (openrouter.ai/keys)
    STRIPE_SECRET_KEY    enables real billing (otherwise mock mode)

  Point Clioloop at this portal:
    export CLIO_PORTAL_BASE_URL=http://localhost:4280
    clio setup
`);
