# POSHOW

A Pokémon-inspired RPG with a retro terminal look. It runs as a web app and as a Telegram bot, both on the same
accounts, the same database and the same Python rules engine, so a battle resolves the same way on either side.

## Features

- **Journey mode** — a connected map of towns and routes, wild encounters, trainers, a rival, eight gyms, the Elite
  Four and a Champion. Campaigns exist for Kanto, Johto, Hoenn and Kalos. The other regions are playable as free-roam
  route scouting without a campaign.
- **Battles** — Fight, Bag, Switch and Run with the real type chart, STAB, critical hits, status conditions, stat
  stages, natures, IVs and EVs. Many abilities have battle effects; the rest are descriptive only.
- **Collection** — catching with several ball types, a team and a storage box, the Pokédex, shinies, level-up move
  learning, and evolution by level, stone or Trade Cable.
- **Progression** — daily boss, endless Battle Gym, EXP All, Rare Candy, shop, care centre, leaderboard.
- **Multiplayer** — PvP battles with team building, team preview and several formats (1v1, 3v3, 6v6, friendly with custom rules), rated matchmaking, player-to-player trading and a market with fixed-price Pokémon listings.
- **In-app help** — an information panel with a guide, update notes and community ideas (players suggest and vote; admins review and edit the content), a connection indicator, and retry-safe purchases.
- **Accounts** — username and password, "Continue with Telegram", Telegram Mini App sign-in from verified `initData`,
  and linking a web account to a Telegram account.
- **Admin tools** — an Admin panel (item grants, scene images), database metrics endpoints, and a bug-report form in Settings.

## Stack

| Part | Technology |
|---|---|
| Web app | Next.js 15, React 19, Tailwind CSS |
| API | FastAPI (`api/index.py`) |
| Game rules | Python modules in `api/_lib`, shared by the API and the bot |
| Bot | python-telegram-bot (polling) |
| Database | Supabase (PostgreSQL) |

## Repository layout

```
app/, components/, lib/, store/, hooks/   web app
api/index.py                              HTTP API
api/_lib/                                 game rules, persistence and data shared by the API and the bot
telegram-bot/                             Telegram bot
database/schema.sql                       database schema and functions
docs/                                     deployment and admin guides
tests/                                    offline test suite
tools/                                    data build scripts and the database benchmark
```

## Run locally

Web app only (an offline game engine runs when no API is configured):

    npm install
    npm run dev

With the API (Python 3.10+):

    pip install -r requirements.txt
    uvicorn api.index:app --reload              # needs SUPABASE_URL and SUPABASE_KEY, see .env.example
    NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev

Telegram bot: see [telegram-bot/README.md](telegram-bot/README.md).

## Configuration

Environment variables are listed in [.env.example](.env.example). The database schema is `database/schema.sql`;
run it in the Supabase SQL editor (it can be re-run safely). Deployment on Vercel, Render and Supabase is described
in [docs/DEPLOY.md](docs/DEPLOY.md); admin setup is in [docs/ADMIN.md](docs/ADMIN.md).

## Tests

    python3 tests/run_all.py

The suite runs offline against stand-ins for Supabase and Telegram. See [tests/README.md](tests/README.md).

## Known limitations

- Only Kanto, Johto, Hoenn and Kalos have campaigns. The Hoenn data was written from memory of the games and has not been checked against a source.
- The battle AI for trainers and bosses is rule-based. A learning policy exists as an opt-in experiment (off by default) and has not beaten the rule-based AI; see docs/AI_REPORT.md.
- The Telegram bot is a lighter companion by design: team building, matchmaking and storage management are web-app only.
- Many abilities and move effects are not implemented.
- The market sells Pokémon at a fixed price only; there are no auctions or item listings.
- The database SQL has only been exercised against a test stand-in, not a live Postgres.
