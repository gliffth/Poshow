# Deployment

```
Browser ──► Vercel (Next.js) ──fetch──► Render (FastAPI) ──REST──► Supabase (PostgreSQL)
                                              ▲
Telegram bot (any always-on host) ────────────┘ same database
```

## 1. Supabase

1. In the SQL editor, run `database/schema.sql`. It never drops tables, so it can be re-run. Re-run it after
   upgrading: it also (re)creates the database functions the API calls.
2. After the API is deployed, open `https://YOUR-API/api/diagnose`. It must report `"ok": true`; otherwise it lists
   the missing table, column or function.
3. Use the `service_role` key on the API and the bot host only. With that key, enable Row Level Security with no
   policies so the public anon key can read nothing (the `accounts` table holds password hashes):

   ```sql
   alter table players enable row level security;
   alter table pokemon enable row level security;
   alter table battle_sessions enable row level security;
   alter table accounts enable row level security;
   alter table login_codes enable row level security;
   ```

   Switch `SUPABASE_KEY` to the `service_role` key first, or the API is locked out as well.

## 2. API (Render)

Create a Blueprint from this repository (it reads `render.yaml`), or a Web Service with an empty root directory,
build command `pip install -r requirements.txt`, start command
`uvicorn api.index:app --host 0.0.0.0 --port $PORT`, and health check path `/api/health`.

Keep one worker (`WEB_CONCURRENCY=1`): request locks are per process.

Create the Supabase project and the Render service in the same region; every request makes one to four database
calls.

### Environment variables

| Variable | Purpose |
|---|---|
| `SUPABASE_URL`, `SUPABASE_KEY` | Database. Required: on Render and Vercel the API refuses to start without them. |
| `BOT_TOKEN` | Verifies Telegram Mini App `initData` and sends Telegram notifications (duel and trade invites, bug reports to admins). |
| `BOT_USERNAME` | Builds the `t.me` links used by Telegram login and account linking. |
| `ADMIN_USERNAMES`, `ADMIN_USER_IDS` | Admin accounts; see [ADMIN.md](ADMIN.md). |
| `AUTH_SECRET` | Optional secret for signing login tokens. Without it a secret derived from `SUPABASE_KEY` is used. In production one of the two must be set. |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins. Default: any. |
| `REQUIRE_AUTH` | Player endpoints verify the login token unless this is `0` (local development only). |
| `ALLOW_MEMORY_MODE` | `1` runs without a database. Progress is lost on restart. |
| `ALLOW_LEGACY_SAVE` | `1` allows a non-atomic save when `save_player_atomic()` is missing. Ignored on Render, Vercel and when `PRODUCTION` is set. |
| `ALLOW_POKEAPI` | `1` lets the API query PokéAPI for species missing from the bundled data. Off by default. |
| `SLOW_REQUEST_MS`, `SLOW_DB_MS`, `DB_TARGET_MS` | Thresholds for slow-request and slow-database-call logs and the database latency target (defaults 1500, 250, 80). |
| `ASSETS_CACHE_S`, `LEADERBOARD_CACHE_S` | Cache lifetimes in seconds (defaults 60 and 15). |

## 3. Web app (Vercel)

Set `NEXT_PUBLIC_API_URL` to the API's URL without a trailing slash, then redeploy: the value is read at build time.
Without it the site calls `/api/...` on its own domain.

## 4. Telegram bot

The bot polls Telegram, so it runs on an always-on host, not on Vercel. See
[../telegram-bot/README.md](../telegram-bot/README.md).

- **Continue with Telegram**: the website shows a one-time code and opens `t.me/<BOT_USERNAME>?start=web_<code>`.
- **Mini App**: set the Mini App or menu button URL in @BotFather to the web app. Players are signed in from
  Telegram's signed `initData`, which the API verifies with `BOT_TOKEN`.
- **Account linking**: Settings → Link Telegram on the website, then `/link CODE` in the bot. Web and Telegram then
  share one player.

## 5. Cold starts on Render's free plan

A free service sleeps after about 15 minutes without traffic, and the next request waits roughly a minute while it
starts. The health check path does not prevent this. Options:

- A paid, always-on instance (reliable).
- `KEEPALIVE_URL` on the bot host: the bot requests `/api/health` every few minutes (see the bot README). It only
  helps while the bot's own host stays running.
- An external uptime monitor requesting `/api/health`.

Keeping a free service awake continuously uses most of the free instance hours; check Render's current limits. The
website shows a "waking up" state instead of switching to offline mode while the API starts.

## 6. Measuring performance

- Every API response carries a `Server-Timing` header: `total`, `db` (time and number of calls), `dbmax` (the slowest
  database operation) and `lock` (time spent waiting for a per-player lock).
- `GET /api/metrics` (admin) reports, since the last restart: request latency per route; database call latency
  (p50, p95, p99) per operation with rows read and written, bytes and errors by kind; connection-pool use; requests and
  database calls per second; lock wait; cache hit rates. Database latency is measured by the API and includes the
  network round trip to Supabase.
- `GET /api/admin/db-health` (admin) returns database-side numbers: connections, lock waits, cache hit ratio, scan
  counts per table and, if the `pg_stat_statements` extension is enabled, the slowest statements. CPU use is not
  available from SQL; read it in the Supabase dashboard.
- `GET /api/admin/db-explain?name=load_player&user_id=<id>` returns the execution plan of one named hot query. Names:
  `load_player`, `load_pokemon`, `player_sessions`, `trades_for_user`, `duels_for_user`, `leaderboard`,
  `account_by_user`, `identity_links`.
- `python3 tools/db_bench.py --api URL --admin NAME:PASSWORD --yes` plays a short session with throwaway accounts
  and prints client-side latency per endpoint, the server's database latency per operation and the execution plans,
  with a comparison against the 80 ms target.
- `python3 tests/bench_roundtrips.py` prints the database calls made by each game action.

Add an index only after `db-explain` shows a sequential scan on a table that is large enough for it to matter.
