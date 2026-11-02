# TurAgent AI — Cloudflare Workers + D1

Start with **[README_UZ.md](README_UZ.md)** for full Windows deployment instructions.

This is a new Cloudflare Workers JavaScript backend replacing the prior Python HTTP server, while retaining TurAgent AI v5.2's frontend. It includes D1 SQL migrations and a secure secrets workflow.

No private `.env` or `.dev.vars` file is shipped. Real payments are NOT implemented; all payment transactions are simulated.

Commands: `npm install`, `npm run db:local`, `npm run dev`, `npm run db:remote`, `npm run deploy`.

Before remote deploy, create D1 and replace the `database_id` placeholder in `wrangler.jsonc`.
