# Running the Telegram bot

If you tried deploying this folder as its own Vercel project and got
`"No python entrypoint found... define an entrypoint in one of: app.py,
index.py, server.py, main.py..."` — that error is real, but fixing the
filename wouldn't actually fix the deployment. Even if Vercel could find
an entrypoint, `bot.py` would still fail to run correctly there, for the
reason below.

`bot.py` here is the actual POSHOW Telegram bot. Not deployed to Vercel —
Vercel Functions are serverless (spin up per request, no persistent
process), and `bot.py` uses `Application.run_polling()`, which needs to
run continuously holding its own connection to Telegram. Those two models
are fundamentally incompatible, no config flag fixes that.

Shares `../api/_lib/` with the Vercel-deployed FastAPI bridge, so the bot
and the Mini App run the exact same battle/catch/currency logic from two
different processes ⚙

ᓚ₍⑅^..^₎♡ where to actually run this

any host that keeps a process alive works:
- Railway / Fly.io / Render — free/cheap tiers, straightforward Python
  deploys, probably least friction
- a small VPS — `pip install -r requirements.txt`, run under `systemd` or
  `tmux`/`screen` so it survives disconnects
- Termux, if that's already your setup — nothing here changes that,
  `bot.py` runs exactly the same, just imports shared modules from one
  directory up now

setup:
```bash
cd telegram-bot
pip install -r requirements.txt
export BOT_TOKEN=your_token_here
export SUPABASE_URL=...   # same project as the web app, so both share one player database
export SUPABASE_KEY=...
python bot.py
```
Omitting `SUPABASE_URL`/`SUPABASE_KEY` runs the bot on in-memory storage —
fine for testing, but progress resets every time the process restarts.
Use the **same** Supabase project/keys as the main `poshow` deployment if
you want a Telegram player and a web player to ever be the same person —
right now they wouldn't be anyway, since the web app's guest identity
(`lib/guestId.ts`) isn't linked to a real Telegram user id yet.

◝(ᵔᗜᵔ)◜ a real next step, not required right now

Telegram bots can run in webhook mode instead of polling — Telegram POSTs
each update to a URL you register, one request per message. That's
actually compatible with serverless, and would let the bot live as
another Vercel Function alongside `api/index.py`. `bot.py` is written
around `run_polling()` though, so this means restructuring it to handle a
single incoming `Update` per invocation instead of managing its own
persistent dispatcher loop — a real refactor, not a config change. Worth
it eventually if you want everything on one platform, not something to
attempt without testing against live Telegram traffic.
