# Poshow — Mini App + Bot

A retro monster-battler web app and a Telegram bot sharing one real rules
engine. No sprites, no game engine — the web app is CSS + real Pokémon
sprites + segmented bar components; the shared battle/catch/XP logic is
plain Python, used by both the bot and the web app's API.

ᓚ₍⑅^..^₎♡ repo layout

```
/app, /components, /lib, /store, /hooks   → Next.js frontend (deploys to Vercel)
/api/index.py                             → FastAPI bridge (deploys to Vercel, same project)
/api/_lib/                                → shared game logic (battle, catch, XP, currency...) —
                                             imported by BOTH api/index.py and telegram-bot/bot.py
/telegram-bot/                            → the actual Telegram bot — does NOT deploy to Vercel,
                                             see telegram-bot/README.md for why and what to use instead
```

ദ്ദി(ᵔᗜᵔ) run locally

frontend only, plays the local mock rules engine, no Python needed:
```bash
npm install
npm run dev
```

frontend + real backend together (matches production, no CORS setup):
```bash
npm install
pip install -r requirements.txt
vercel dev
```
runs Next.js and the FastAPI bridge on one origin, same as they'll run on
Vercel. Open `http://localhost:3000`.

telegram bot — see `telegram-bot/README.md`, runs completely separately,
it's a persistent process, not something `vercel dev` starts.

⚙ deploying — one Vercel project for the app + API

Already structured for Vercel's zero-config Next.js + Python pattern:
Next.js at the repo root, FastAPI at `api/index.py`. No `vercel.json`
needed — Vercel detects both frameworks and routes `/api/*` to the Python
function, everything else to Next.js. One domain, so the frontend's
relative `/api/...` calls just work.

1. Push to GitHub, import in Vercel, deploy — genuinely it for frontend + API.
2. Set `SUPABASE_URL` and `SUPABASE_KEY` as real Vercel Environment
   Variables — not optional once deployed, see the warning at the top of
   `api/index.py` (serverless functions don't reliably share memory across
   requests, so without a real database, player data and battle sessions
   can behave inconsistently under real traffic).
3. Run the SQL in `api/index.py`'s docstring once in your Supabase SQL
   editor to create the `battle_sessions` table.
4. The Telegram bot is a separate deployment, never touches this Vercel
   project — see `telegram-bot/README.md`.

◝(ᵔᗜᵔ)◜ the web app

play loop: Roster → Scan Area → wild encounter → Fight / Bag (balls +
potions) / Switch / Run → XP, level-ups, move-learning, currency reward or
capture → back to Roster. Pokédex, Shop, Profile, Settings all reachable
from the bottom dock anytime (battle screen hides the dock mid-fight). The
Roster screen shows a thumbnail strip of the party — tap one to bring it
into the main viewport below, instead of every monster getting its own
stacked card.

themes: three selectable palettes, switchable anytime in Settings, no
reload — `weathered` (default, worn hardware terminal, desaturated, dark),
`cream` (warm Game Boy cartridge), `paper` (aged sepia parchment). Pure CSS
variable swaps (`app/globals.css`'s `[data-theme="…"]` blocks), no
component ever branches on which one's active. Lives in
`state.settings.theme`, persisted, applied via
`components/terminal/ThemeSync.tsx`. Known limitation: theme's only known
after React hydrates, so a saved cream/paper choice flashes the weathered
default first — fixable with an SSR-readable cookie, not done here.

species data and sprites: real Pokémon data, not fictional placeholders —
16 species spanning most early routes/types (`lib/gameData.ts`'s
`SPECIES_DB`), real base stats, curated level-appropriate movesets,
precomputed dual-type effectiveness (credit: the `Pokego` reference
project). Sprites are real Showdown-style battle GIFs keyed by national
dex number, from PokeAPI's public sprite repo — same source for
local-fallback monsters and server-backed ones (`pokedex_id` now included
in `api/index.py`'s response). To add more species: pull a species JSON
from a PokeAPI-shaped dataset, extract stats/moves/`type_effectiveness.multipliers`/sprite
URL, add an entry to `SPECIES_DB` — nothing downstream needs touching.
Damage formula now matches real Pokémon math (verified against Showdown's
calculator), including STAB, which was missing before.

where things live:
- `lib/types.ts` — every shared type (Monster, Move, GameState, BattleState…)
- `lib/gameData.ts` — real species roster, move database, type effectiveness
  fallback chart, wild encounter table, shop catalog — the local fallback,
  used when the real backend isn't reachable
- `lib/battleEngine.ts` — pure combat math for the local fallback: damage
  formula, catch odds, XP/level-up curve, status gating, enemy AI
- `lib/apiClient.ts` — typed client for `api/index.py` + the server→frontend Pokémon mapper
- `lib/guestId.ts` — temporary placeholder trainer identity (see rough edges below)
- `lib/sound.ts` — procedural 8-bit SFX via Web Audio, no audio files
- `lib/storage.ts` — localStorage save/load, guarded for SSR
- `store/reducer.ts` + `store/GameContext.tsx` — single source of truth.
  `GameContext` exposes `actions.scanArea / playerMove / catchAttempt / flee`,
  real backend when reachable, local reducer/engine fallback when not
- `components/terminal/` — reusable chrome: `SegmentedBar`, `IconDock`,
  `TerminalLog`, `TopBar`, `BoltCorners`, `RosterStrip`, `ThemeSync`
- `components/*Screen.tsx` — Roster, Battle, Pokedex, Shop, Settings, Profile

backend wiring status — real, not just planned. `GameContext`'s actions
call `api/index.py` when reachable (checked via `/api/health`), fall back
to the local mock engine when not.

fixed since the first wiring pass ✧:
- roster reconciliation — first successful server connection replaces the
  local mock starters wholesale with the real backend roster, once
  (`hasReconciledServer`), no more duplicate/orphaned starters
- switch + in-battle healing hit the real backend now — `/api/battle/switch`
  and `/api/battle/item` are real endpoints. one honest simplification:
  real games punish a voluntary switch with a free enemy hit, reproducing
  that meant duplicating `battle_system.py`'s damage logic, so switching is
  free here for now — documented in `battle_switch`'s docstring, not
  silently passed off as matching the real rules
- shop is real — `/api/shop/buy` prices server-side (never trusts a client
  price), spends real coins, adds real items to the actual inventory
- healing outside battle — there was previously no way to heal a Pokemon
  from the Roster screen, and fainted (0 HP) Pokemon couldn't enter or be
  switched into a battle to get healed there either, so a fainted Pokemon
  had no path back at all. `POST /api/party/heal` (and the local
  `HEAL_PARTY_MEMBER` reducer case) fix this — Potions/Superpotions work
  from the Roster screen now, on any team member, fainted or not. One
  simplification: real games need a separate Revive item to heal a
  fainted Pokemon; a regular Potion doing it here is a deliberate
  shortcut, not an attempt to model that mechanic exactly

still open, flagged on purpose ⤙•:
- PP is fake for server battles — the bot doesn't track per-move PP, so
  server moves show `99/99` as an explicit "not tracked" sentinel, and
  show the move's type instead of a PP count so it doesn't read as a real
  number that mysteriously never depletes
- guest identity is a random localStorage int, not a real Telegram user —
  `lib/guestId.ts` is explicitly temporary, real Telegram `initData` auth
  is what turns this into an actual Mini App instead of a website next to a bot
- catch rate is still a flat placeholder (`45`) — real per-species rates
  exist in PokeAPI's species endpoint but `pokeapi_manager.py` doesn't fetch it
- still haven't run any of this end-to-end — no network access here means
  no real `pip install`/`npm install` against live registries, so this is
  verified by compiling clean + careful manual review, not by clicking
  through a live battle. deploying to your VPS is the real test, send me
  whatever breaks
