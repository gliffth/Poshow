# Running the Telegram bot

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
export SUPABASE_URL=...   # optional — omit to run on in-memory player storage
export SUPABASE_KEY=...
python bot.py
```

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
