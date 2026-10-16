# Deploying POSHOW (Vercel website + Render API + Supabase)

```
 Browser ──► Vercel (Next.js site)  ──fetch──►  Render (FastAPI)  ──REST──►  Supabase (Postgres)
                                                       ▲
 Telegram bot (any host) ───────────────────────────────┘ same database
```

## 1. Supabase — once
1. SQL Editor → paste **`database/schema.sql`** → Run. It never drops your data, so it is safe to re-run.
   (The old `poshow-schema.sql` is gone: it didn't match the code. That mismatch caused the
   `created_date` error, teams vanishing, and battles returning 404.)
2. After the API is deployed, open **`https://YOUR-APP.onrender.com/api/diagnose`**. It must say `"ok": true`.
   If not, it lists exactly which table/column is wrong.

## 2. Render (API)
- Easiest: New → **Blueprint** → this repo (reads `render.yaml`). Or a Web Service with:
  Root Directory **empty**, Build `pip install -r requirements.txt`,
  Start `uvicorn api.index:app --host 0.0.0.0 --port $PORT`, Health Check Path `/api/health`.
- Environment: `SUPABASE_URL`, `SUPABASE_KEY`, `BOT_USERNAME` (see `.env.example`).

### Keeping it awake (cold starts)
Render's **free** plan puts a service to sleep after ~15 minutes without incoming traffic, and the next request
waits ~30-60 s while it boots. The *Health Check Path* setting does **not** prevent this — it only tells Render
whether a deploy is healthy. What works:
- **A free uptime pinger**: UptimeRobot (HTTP monitor, 5-minute interval) or cron-job.org (every 10 min) hitting
  `https://YOUR-APP.onrender.com/api/health`. The endpoint is tiny and never touches the database.
  One free service uses ~744 of the 750 free instance-hours a month, so it stays inside the free allowance.
- Or Render's paid plan (no sleeping).
- The website also pings every 20 s while a tab is open, and shows "Waking up the server…" (instead of
  silently dropping to offline mode) during a cold start.

## 3. Vercel (website)
- Environment Variable **`NEXT_PUBLIC_API_URL`** = `https://YOUR-APP.onrender.com` (no trailing slash), then **redeploy**
  (it is baked in at build time — changing it without redeploying does nothing).
- Without it the site calls `/api/...` on the Vercel domain, finds nothing, and shows the "no signal" icon.

## 4. Telegram bot
Runs separately (`python telegram-bot/bot.py`) with `BOT_TOKEN`, `SUPABASE_URL`, `SUPABASE_KEY`.
Website → "Continue with Telegram" gives a one-time code and opens `t.me/<BOT_USERNAME>?start=web_<code>`.
Web and bot then share one player (same Telegram id).

## 5. Secrets — please do this
- A real Supabase URL + **anon key** used to be hardcoded in `api/_lib/database.py` (now removed). If this repo is
  or ever was public, **rotate that key** (Supabase → Project Settings → API) and use the **service_role** key on
  Render/the bot host only.
- With the service_role key you can (and should) turn on Row Level Security with no policies, so the public anon key
  can read nothing — the `accounts` table holds password hashes:
  ```sql
  alter table players enable row level security;
  alter table pokemon enable row level security;
  alter table battle_sessions enable row level security;
  alter table accounts enable row level security;
  alter table login_codes enable row level security;
  ```
  Only do this AFTER switching `SUPABASE_KEY` to the service_role key, or the API will be locked out too.


## Environment variables added since (Render)
| Variable | Purpose |
|---|---|
| `REQUIRE_AUTH` | leave unset = ON. Every player endpoint verifies the signed login token. Set `0` only for local dev |
| `ADMIN_USERNAMES` / `ADMIN_USER_IDS` | who gets the Admin panel (see docs/ADMIN.md) |
| `BOT_TOKEN` | optional on the API: lets it DM Telegram players about duel/trade invites |
| `ALLOW_MEMORY_MODE` | set `1` ONLY to run deliberately without Supabase; otherwise Render/Vercel refuse to start without it |
| `WEB_CONCURRENCY` | keep `1` (the request lock is per process) |


## Upgrading the database (required for this version)

Run `database/schema.sql` again in the Supabase SQL editor (safe to re-run). It adds `players.version`,
`pokemon.pending_moves` and the `save_player_atomic()` function that makes every save one transaction with a
version check. Then open `/api/diagnose` — it must say `"ok": true` (it also checks the function exists).
Until then saves fail loudly with a schema error instead of silently dropping data. `ALLOW_LEGACY_SAVE=1`
re-enables the old non-atomic save temporarily if you must keep playing while you migrate.


## One player across web and Telegram

1. Re-run `database/schema.sql` (adds `identity_links`, `login_codes.link_user_id`, `feedback`, `link_identity()`); `/api/diagnose` must say ok.
2. API env: `BOT_TOKEN` so it can verify Mini App `initData`; `BOT_USERNAME` for the deep links.
3. @BotFather: set the Mini App / menu button URL to the web app.
4. Players link in Settings → Link Telegram, or with `/link CODE` in the bot.
