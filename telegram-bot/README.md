# Telegram bot

`bot.py` is the Telegram front end of POSHOW. It uses long polling (`Application.run_polling()`), so it needs a
host that keeps a process running. It cannot run as a serverless function (Vercel).

It imports the shared game modules from `../api/_lib`, so the bot and the API use the same rules and the same
Supabase database.

## Run

    cd telegram-bot
    pip install -r requirements.txt
    export BOT_TOKEN=...          # from @BotFather
    export SUPABASE_URL=...       # same project as the API
    export SUPABASE_KEY=...
    python bot.py

Any host that keeps a process alive works: a VPS (under systemd, tmux or screen), Render, Railway, Fly.io, Termux.

Without `SUPABASE_URL` and `SUPABASE_KEY` the bot uses in-memory storage and loses progress on restart.

## Optional settings

| Variable | Purpose |
|---|---|
| `KEEPALIVE_URL` | API base URL. The bot requests its `/api/health` every `KEEPALIVE_INTERVAL` seconds (default 600, clamped to 60–840) so a free-tier API does not sleep. Only useful if the bot's own host stays running. |
| `ADMIN_USER_IDS`, `ADMIN_USERNAMES` | Who may use the admin commands (see [docs/ADMIN.md](../docs/ADMIN.md)). |

## Accounts

- `/weblogin CODE` confirms a "Continue with Telegram" login started on the website.
- `/link CODE` joins a web account to this Telegram account (code from Settings → Link Telegram on the website).
  If both already have Pokémon, the bot asks which to keep with `/link CODE keep web` or `/link CODE keep telegram`;
  the other side is archived, not deleted.
