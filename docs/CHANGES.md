# Changes — persistence & mechanics audit round

Persistence: fail-closed battle sessions, no ghost players, atomic + versioned saves (`save_player_atomic`),
strict schema, fail-closed PvP/trade store, visible bot save errors, 409 on concurrent edits.
Mechanics: HP `+level+10`, level-up no longer a full heal, stable abilities across reloads, level-up move learning
(+ `/api/party/learn-move`), voluntary switch costs the turn, Gen 5+ catch formula with real ball rules, ~25 more
real abilities. Tests: location-independent, `tests/run_all.py`, new suites (persistence, move learning, switch,
catch, extra abilities). See `docs/BUGS.md` #30–#45.

# What changed vs. poshow-final (and why)

## Root cause of the broken/"disorientated" UI (screenshot from poshow-*.vercel.app)
poshow-final replaced/removed files the Next.js build depends on:
- `postcss.config.mjs` removed -> Tailwind 4 never compiled -> unstyled page, giant sprite
- `tsconfig.json` replaced with a Vite-style one (needs a missing tsconfig.node.json, wrong jsx mode, no Next plugin)
- `next.config.ts` replaced by `next.config.js` -> lost `images.remotePatterns` (sprites blocked) and `output: standalone`
- `.gitignore`, `eslint.config.mjs`, root `requirements.txt` (Vercel Python deps) removed
All restored from your original terminal-battler.

## Telegram bot
poshow-final overwrote your 1,381-line bot (hunt, PvP, shop, switching, catching, moves, pokedex)
with a 438-line stub that used in-memory state and fake battles. The ORIGINAL bot is restored untouched.
The stub's route table is kept as `telegram-bot/route_data.py` (not wired in yet).

## Added (additive only)
- api/_lib: abilities_system, exp_all_system, daily_boss_system, rare_candy_system, route_encounters
- currency_system: superset (adds exp_all / rare_candy prices)
- API: `GET /api/boss/today`, `POST /api/party/rare-candy`, `rare_candy` in shop prices
- database/ (schema + SQL notes), PokeDex/ data, `.vercelignore` (keeps PokeDex/bot out of the serverless bundle)

## Fixed in the new modules
- daily boss reseeded the global `random` (racy) -> private RNG
- rare candy left stale XP after level-up -> resets it
- invalid species: `sprig` -> `bellsprout`; `nidoran_m/f` -> `nidoran-m/f`

## Deliberately NOT taken from poshow-final
- trading_system.py (shrunk 14.5KB -> 6.7KB, lost functionality) -> original kept
- pokemon_model.py ability edit (random ability from PokeAPI; unverified, unused) -> original kept
- docs claiming "tested / 99.9% SLA / production ready"

## Not done yet (needs your decision)
- API has no auth: `user_id` is trusted from the request body, CORS is `*`
- Boss fight, EXP All, routes and abilities are modules only - not connected to the battle flow / UI / bot
- I could not run `npm install`/`next build`, FastAPI or python-telegram-bot here (no network) - only Python compile checks and module tests

---

# Round 2 — features wired end to end (API + web UI + Telegram bot)

All four features now run in the real battle flow, not just as modules. Shared rules live in
`api/_lib/boss_battle.py` so the web app and the bot behave identically.

## Routes
- API: `GET /api/routes`; `route_id` accepted by `/api/encounter/scout` and `/api/battle/start`
- Web: "Location" dropdown on the Scan screen (default = the original level-scaled wild grass mix)
- Bot: `/routes` + menu button; the choice sticks for `/hunt` until you pick "Wild Grass" again
- Per-route level ranges (Route 1 = Lv 3-8 ... Route 10 = Lv 22-28) instead of one flat 3-15

## Abilities
- Every Pokémon now has an ability derived from its species (first PokeAPI ability we define, else a
  type default: Blaze/Torrent/Overgrow/Static). Nothing new is stored in the database.
- Applied inside `BattleSystem._execute_move` for both sides, so web and bot get it automatically:
  Blaze/Torrent/Overgrow/Static-style boosts, Volt/Water Absorb, Flash Fire, Filter, Multiscale, Sturdy,
  Intimidate, Guts, Shell Armor, Snow Cloak, Magic Bounce. Wrapped so a bad ability can never break a turn.
- Shown on the stat card (web) and in the battle panel (bot); the log says when an ability triggers.

## EXP All
- Shop item (500 credits) on web (`Special Gear`) and bot (`/buy exp_all 1`)
- Web: toggle in the battle Bag; Bot: "EXP ALL" button in the battle. On a win, XP is split across the
  healthy team and ONE is consumed. Losing never consumes it. Win screen shows the split.

## Daily boss
- `GET /api/boss/today?user_id=`, `POST /api/boss/start`; web card on the Roster; bot `/boss`
- Rotates at 00:00 UTC (same boss for everyone, API and bot agree). Scaled to your lead Pokémon
  (never > 6 levels above it). Uncatchable. One reward per day (claim is stored in the player's
  inventory JSON as `_boss_last_win`, hidden from all inventory lists - no DB migration needed).
- Rewards: credits + XP + drops (Rare Candy / EXP All). Flawless bonus if you lose < 50% HP.

## Rare Candy
- Shop item (1000), `POST /api/party/rare-candy`, button on the Roster when you own one, `/candy [slot]` in the bot.

## Bugs found and fixed while wiring (existing code)
- `/api/roster` returned HTTP 500 for any Pokémon whose types came as plain strings (PokeAPI manager format)
- Base stats were silently all 50 for species fetched through `pokeapi_manager` (flat `base_stats` dict
  was never read, only the raw `stats` list)
- Daily boss reseeded the global RNG; Rare Candy left stale XP; invalid species in route data

## Verified vs not verified
Verified offline (no network here): 40+ checks across `test_api` / `test_abilities` / `test_bot`
(routes, scout, shop, EXP All split + consume, boss start/claim/uncatchable/second-attempt-blocked, candy,
every ability, bot hunt/boss/EXP All/catch-block/inventory/buy flows) using stub FastAPI/Telegram/DB and
fake PokeAPI data.
NOT verified: `npm install` / `next build`, real Supabase, real Telegram. The TypeScript was type-checked
without React types installed, so only real logic errors (one, already fixed) could be seen. Please check the
Vercel preview build log on first deploy.

## Tuning knobs
- Boss payout is generous next to wild fights (~1,350 credits at Lv18 vs 10-50 for a wild win).
  Change `coin_reward` / `xp_reward` in `api/_lib/daily_boss_system.py`.
- Boss scaling: `BOSS_LEVEL_LEAD` / `BOSS_MIN_LEVEL` in `api/_lib/boss_battle.py`.

---

# Round 3 — Battle Gym (endless gym circuit)

Poshow's own take on the "endless tower" idea: **Battle Gym**. Original leaders, badges, BP shop.

- **Floors:** every floor is one gym trainer; every 5th floor is a Gym Leader (10 original leaders, looping:
  Warden Cinder / Ember, Tidecaller Mira / Tide, Thornwick / Thicket, Voltmaster Jun / Spark, Cairn / Cairn,
  Seer Ophel / Mind, Frostbound Neve / Frost, Wyrmkeeper Rao / Wyrm, Brawler Kesh / Fist, Hollow Marrow / Hollow).
- **Scaling:** opponent level = 8 + 2 x floor (+3 for leaders), capped at 100. It scales with the floor, not
  with you, so you have to train to go deeper. Leaders have perfect IVs and a signature ability.
- **Rules:** no XP in the gym; whole team is healed after each cleared floor; a fainted Pokémon stays down until
  the floor is cleared (send in the next one); run ends when everyone has fainted or you forfeit (Run/Forfeit).
  Gym Pokémon can't be caught. A floor's opponent is the same on every retry (per-run seed).
- **Rewards:** Battle Points (1 + floor/5, +5 for a leader) and credits (12 x floor, +60 for a leader);
  leader floors award "<Gym> Badge" (stored in the existing `badges` field).
- **Gym Shop (BP):** Super Potion 4, Great Ball 4, Ultra Ball 8, EXP All 20, Rare Candy 30.
- **No DB migration:** state is kept in the player's inventory JSON (`_gym_floor`, `_gym_best`, `_gym_seed`,
  `battle_points`); internal keys are hidden from every inventory list.
- **API:** `GET /api/gym/status`, `POST /api/gym/enter` (start / next floor / next Pokémon),
  `POST /api/gym/forfeit`, `POST /api/gym/shop/buy`; `/api/battle/move` and `/api/battle/flee` understand gym fights.
- **Web:** Battle Gym card on the Roster, "Next Floor" inside the battle screen, Gym Shop section on Shop.
- **Bot:** `/gym` + menu button, floor fights through the normal battle screen, `Gym shop` buttons.
  Note: sending in your next healthy Pokémon moves it to the front of your team (same as using Switch).
- Shared rules live in `api/_lib/gym_system.py` (used by both API and bot).

Not included (needs a DB table, so it's your call): a global leaderboard of best floors.
Personal best is tracked per player.

---

# Round 4 — "why is nothing saving / logging in?" (diagnosis + accounts + starter flow)

## Root causes found (from your Render logs + screenshots)
1. **Wrong SQL was run.** `poshow-schema.sql` (from poshow-final) doesn't match the code: `players` had no
   `created_date`, `pokemon` had no `trainer_id`, `battle_sessions` had different columns. Result:
   - `Save failed: Could not find the 'created_date' column` (the error in your logs)
   - Pokémon rows silently failed to save (the code didn't log that failure) -> "Loaded player with 0 Pokémon"
   - battle sessions silently failed to save -> `POST /api/battle/move 404`
   - a player with an empty team got a brand-new Charmander on every request -> "Pokémon changes on refresh"
   Fixed with one authoritative, re-runnable `database/schema.sql` (old file deleted), every DB failure now logged
   with Supabase's own message, and **`GET /api/diagnose`** which tells you exactly what is missing.
2. **The site was playing a local demo** (a random guest id + hardcoded Charmander/Squirtle). It never asked who you were.
3. The "no signal" icon = site couldn't reach the API. It needs `NEXT_PUBLIC_API_URL` on Vercel (redeploy after).

## Persistence
- `save_player()` now saves stats + team ids + every Pokémon in two upserts; logs real error text.
- A database outage raises a clean 503 and can NEVER be mistaken for "new player" (that was how real progress could be overwritten).

## Accounts + onboarding (what you asked for)
- First open -> **Create account / Log in / Continue with Telegram** (username + password, no email).
- Telegram: site shows a code + "Open the Telegram bot" (`t.me/<BOT_USERNAME>?start=web_<code>`); bot confirms; site signs in.
  Telegram players keep their Telegram id, so web and bot share one team. Fallback: `/weblogin CODE` in the bot.
- New account -> **choose a region (9) -> choose a starter (3 each)**, shown over your lab pixel art
  (`public/starter-lab.jpg`) with animated sprites. No more automatic Charmander.
- Region choice sets the player's region; `/api/routes?region=` lists that region's routes
  (Kanto 18, Johto 5, Hoenn 2, Sinnoh/Unova/Kalos/Alola/Galar/Paldea 1 each from `route_data.py`).
- Trainer name = your username (no more "OPERATOR"). Settings -> Account -> Log out.
- Passwords: salted scrypt. Tokens: signed, 30 days, stateless. Login throttling: 8 failures / 10 min.

## Cold starts / "no signal"
- `/`, `/health`, `/api/health` answer instantly (GET and HEAD, no database) for pingers and Render's checks.
- The site now waits up to 65 s for the first health check, shows **"Waking up the server..."** instead of silently
  dropping to offline mode, and one failed poll no longer flips a working connection to offline.
- `render.yaml` blueprint + `docs/DEPLOY.md`. Note: Render's health-check setting does NOT keep a free service awake;
  use a free pinger (UptimeRobot / cron-job.org) — see DEPLOY.md.

## Security
- Removed a hardcoded Supabase URL + key from `api/_lib/database.py` (now env vars only). **Rotate that key if the repo is/was public.**
- Optional `ALLOWED_ORIGINS` for CORS.
- NOT done: the API still doesn't *require* the login token on gameplay endpoints (it is issued and sent by the site).
  Web account ids are random 13-digit numbers so they can't be guessed, but Telegram ids can. Enforcement needs a
  middleware I couldn't test offline — say the word and I'll add it behind a switch.

## Tests (offline, fake Supabase imitating PostgREST)
`test_db` proves: same Pokémon on every reload, battles work, outage != new player, and that the wrong schema is caught
by /api/diagnose. Plus auth/starter/region, bot web-login, and all earlier suites. Frontend type-checked without React types.

---

# Round 5 — Journey engine (Kanto), avatars, Telegram onboarding parity

**RE-RUN `database/schema.sql`** (adds `players.avatar` and `players.story`). Until you do, the game still saves
(without those two fields) and logs a loud warning; `/api/diagnose` lists the missing columns.

## Journey engine (`api/_lib/journey.py`) — data-driven
- Locations are a graph of towns and routes with unlock rules; **Kanto is fully mapped**:
  Pallet Town -> Route 1 -> Viridian City -> Route 2 -> Viridian Forest -> Pewter City (Brock) -> Routes 3-4 ->
  Cerulean City (Misty, rival) -> Routes 5-6 -> Vermilion City (Lt. Surge, rival) -> Route 7 -> Celadon City (Erika) ->
  Route 8 -> Fuchsia City (Koga) -> Routes 9-10 -> Saffron City (Sabrina) -> Cinnabar Island (Blaine) ->
  Viridian City (Giovanni) -> Victory Road (needs 8 badges) -> Indigo Plateau (Elite Four + Champion).
- Wild Pokémon depend on WHERE YOU ARE (a route's encounter table); towns have none. Pokémon Centers heal in towns.
- Story trainers have real multi-Pokémon teams. XP for every Pokémon you beat; EXP All is consumed once per trainer battle.
  Opponents get a sensible STAB moveset (the species' default moves are alphabetical PokeAPI entries).
  The rival's team counters your starter. Elite Four / Champion / Giovanni use perfect IVs.
- Fainted lead with others left: "send the next one" (the trainer's progress is kept). Whole team down: blackout —
  you wake up healed in the last town you reached. No catching, no running from trainer battles.
- Beating the Champion: Hall of Fame, region marked complete, next region unlocked.
- Regions without a map yet (everything except Kanto) stay in **free roam**: the old route picker, nothing gated.
- Existing players get a story automatically the first time it's needed. State lives in `players.story` (jsonb).
- API: `GET /api/journey/state`, `POST /api/journey/travel`, `/heal`, `/trainer/start`; trainer logic is hooked into
  `/api/battle/move` (advance to next Pokémon, win, lose).

## Avatars (`api/_lib/avatars.py`)
- Six original pixel-art trainers generated from code (no image files, nothing to license): `GET /api/avatars/<id>.png`.
- Shared by web (starter screen, top bar) and bot (picker image); later they become the protagonist in story scenes.

## Onboarding, shared by web and Telegram (`api/_lib/onboarding.py`)
- Both now go avatar -> region -> starter -> professor. Telegram previously offered only three Kanto starters.
- The bot also handles old `starter_<name>` buttons (-> Kanto).

## UI
- Web: Journey card on the Roster (location, objective, badges, trainers, heal, travel buttons with lock reasons);
  Scan is disabled in towns; the route picker hides on a journey; trainer name/progress banner and win/lose panels in battle.
- Telegram: `/journey` + menu button with the same actions; trainer battles use the normal battle screen.

## Not done (by design for this slice)
- Scene player / story scenes (next), rival/NPC dialogue scenes, route trainers, evolution, PP/status/nature mechanics,
  hard AI, PvP, the other 8 regions' maps (only the starter + route data exists for them).
- Kanto trainer levels are the originals (Elite Four ~55-62), so the endgame needs real training.
- Tested offline with stubs/fake Supabase (no real FastAPI/Telegram/Next build). The web UI was only type-checked.


---

# Round 6 — admin, care, scenery, real battle rules, evolution

**Re-run `database/schema.sql`** (adds `site_assets`; safe to re-run). Set `ADMIN_USERNAMES` / `ADMIN_USER_IDS` — see `docs/ADMIN.md`.

## Admin system
Give coins / items / Poké Balls / a Pokémon / a full heal to a player **by username** (web Settings → Admin, or `/give`, `/whois` in
Telegram). Admin status is verified server-side from the signed token. Admins can also set the images scenes use.

## Starter kit + gentler bosses
- New trainers start with **300 credits and 2 Potions**.
- Daily bosses are **tiered by your lead's level** — a fresh trainer meets an Onix or Pidgeotto (+2 levels), never a Dragonite. Late-game
  tier (50+) brings back Dragonite/Articuno/Alakazam. Early tiers pay modest rewards.

## Condition, injury and the Care Center
- A Pokémon no longer "dies" on its first knockout. HP is for the fight; **condition** is its life. Each knockout costs 1 condition point.
  Lv5 starters have 3, a Lv60 dragon 10+ — strong Pokémon don't die easily. Shown as a small bar plus "KO left" on the stat card, in the
  Care Center and in Telegram.
- States: Healthy / Hurt / **Severely injured** (0 HP, still has condition) / **Critical** (0 condition) / Resting.
- **Nurse Joy's Care Center** (Roster card + `/care`): free check-up heals HP and restores condition (towns on a journey; anywhere in
  free-roam regions); **intensive care** for critical Pokémon costs credits and usually works (~60-90%, better for stronger/higher-level
  Pokémon); a **Revive** is guaranteed; and if you have no usable Pokémon and no money, Joy treats it for free (no soft-locks).
- **Sleep in ball**: put a Pokémon to rest — about 2% HP per minute and a condition point every 15 minutes, even while you are away.
- Not available during a battle (the server checks).

## Scenery and cutscenes (original, drawn from code)
- `GET /api/scenes/<region|route|town|care|lab>.png|.gif` and `/api/scenes/slide/<region>.png` — pixel art for all nine regions,
  routes, towns, the Care Center (with Nurse Joy) and the lab, plus 12-frame walking GIFs. No image files, nothing to license.
- Web: starter flow is now **trainer -> region slideshow (all nine, auto-advancing, with their starters bobbing) -> "Begin in <region>" ->
  Professor welcome -> choose partner**. Travelling shows a short walking cutscene (tap to skip).
- Telegram: after choosing a trainer you get an **album of all nine region pictures first**, then the question; the chosen region plays an
  animated cutscene; the chosen starter appears as an animated sprite; travelling sends a walking GIF. `/scenes` turns it off.
- Removed the stray welcome photo that appeared during region selection.

## Settings
- **Screen flicker & pulsing** toggle (CRT flicker, moving scanlines, blinking dots; also off automatically for "reduce motion").
- **Cutscenes** toggle.

## Battle rules (engine rewritten — web and bot share it)
- Real **stats** (before, the Telegram bot's battles ignored every Pokémon's stats and used 10/10/50!), **natures** (+10%/-10%), the
  **physical/special split**, a full **18-type chart with immunities** (Ground can't be hit by Electric, Normal can't hit Ghost…), **STAB**,
  stat **stages**, accuracy/evasion, **priority**.
- **PP** per move (Struggle when out), **status**: burn, poison, toxic, paralysis, sleep, freeze, confusion, flinch; secondary effects, drain,
  recoil, healing, recharge, self-KO. Move data (power/accuracy/PP/effects) comes from the real PokeDex (`tools/build_data.py`).
- **Damage now sticks**: the bot never wrote HP back to your Pokémon, so nothing ever stayed hurt; now it does.
- **XP curve fixed**: the old one needed 204,800 XP for Lv12->13. Now level n takes ~0.8*n^3 total.
- Wild/trainer Pokémon get sensible STAB movesets (the PokeAPI default was the first alphabetical moves: "absorb", "acid"...).
- **Opponent AI** for trainers, gym leaders, bosses and the Elite Four: scores every move by expected damage, KOs, priority, status,
  setup and healing, avoids self-KO; wild Pokémon stay random.

## Evolution
Level, **evolution stones** (800 credits), and the **Trade Cable** (1500 — stands in for a trade: Kadabra, Machoke, Graveler, Haunter,
Onix…). Keeps id, IVs, nature, shininess, XP, moves and custom nickname. Roster shows an Evolve button; `/evolve` in Telegram;
438 species with evolutions from the PokeDex. Never during a battle.

## Not done
- Real Pokémon-to-Pokémon player trading and PvP; journey maps for regions other than Kanto; full Gen 9 ability/move-effect coverage;
  a learning battle AI; held items. The scenery is procedural pixel art — if you want photo-style scenes, set them in the admin panel.
- Tested offline with stand-ins (no real FastAPI / Telegram / Next build); the website was type-checked only.


---

# Round 7 — stability, integrity, real data, PvP and trading

See **docs/BUGS.md** (every reported issue + status) and **docs/STATUS.md** (done / left). Re-run `database/schema.sql`.

- Integrity: canonical Pokémon loader, HP clamp, fail-closed persistence, signed encounters, one battle per player, serialized state changes, ownership checks on every player endpoint (default ON), fail-closed routes/species, no silent memory mode.
- Real data: offline species table (types, stats, capture rates, ability slots incl. hidden, level-up learnsets) compiled by `tools/build_data.py` + `tools/build_pokego.py` from the PokeDex and a PokeAPI-derived reference dump; ability descriptions from the PokeDex.
- Battle: real cartridge-style catch formula; event abilities + weather; multi-hit, False Swipe, Facade; retro glyph logs; recoil/drain use damage dealt.
- Progression: `evolution_pending` from every XP source; evolution cutscene; Rare Candy through the same level-up path.
- PvP (3v3 simultaneous turns, switching, ELO, leaderboard, forfeit/timeout) and P2P trading (lock -> confirm swap, atomic with rollback, trade evolutions) — API, web panel, Telegram invites.
