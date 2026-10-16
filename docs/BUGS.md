# Bug & issue tracker

Every issue reported so far (your testers' screenshots + the four external audits), with its status.
**Fixed** = changed in this codebase AND covered by an automated test (offline stand-ins; confirm on your first deploy).
**Open** = not done — listed honestly in the second table.

## Fixed

| # | Issue | Fix | Test |
|---|---|---|---|
| 1 | Recoil killed the attacker (354 dmg on a 24-HP target -> 88 recoil) | recoil/drain use HP actually taken, not overkill; log shows real damage | test_p0 |
| 2 | HP "sometimes shows one thing, sometimes another"; **Greninja 90 / 85 HP** | ONE canonical `PokemonInstance.from_dict` (restore -> recalc stats -> clamp HP) used by DB rows and battle sessions; HP clamped in `recalculate_stats` | test_p0, test_integrity |
| 3 | "Pokémon isn't dealing damage" / wrong move used | invalid move = 400 (never silently the first move); the random 1-20 damage fallback is gone; real stats/physical-special split | test_p0, test_rules |
| 4 | Slowness (PokeAPI on every turn) | offline species data (types/stats/abilities/capture rates/learnsets) — hot paths never touch the network | test_p0 (network disabled) |
| 5 | Gym: the starter comes back every floor | switching moves the new Pokémon to the front; next floor/trainer starts with it | test_p0 |
| 6 | Caught Pokémon missing from Pokédex / roster | catch response returns the Pokémon, Pokédex, collection; client re-syncs roster; roster exposes Pokédex + storage | test_p0 |
| 7 | **Poké Balls guaranteed catches** (clamped to 100%) | cartridge-style capture formula, real per-species capture rates, status bonus, ball ids normalised (Great/Ultra balls had no effect) | test_p0 |
| 8 | Bayleef Lv42 never evolved | server reports `evolution_pending` after battle XP / Rare Candy; evolution scene + Evolve button; one atomic evolve call | test_integrity, test_evolution |
| 9 | Evolution bypassed by EXP All / Rare Candy | Rare Candy now levels through `add_experience`; every XP source ends in the same `progression.pending()` check | test_integrity |
| 10 | DB read failure became an **empty roster** | pokemon lookup failure raises DatabaseError (503) | test_db |
| 11 | A Pokémon silently dropped when it failed to load | load failure raises; team ids missing from the table are logged | test_db |
| 12 | Save failures only logged — "caught!" while unsaved | `persist_player` raises; battle session deleted only after a successful save | test_db |
| 13 | Two loaders for Pokémon (`load_player` / `get_player_pokemon`) | both use the canonical loader | test_integrity |
| 14 | Generic 45/49/49 stats when a lookup failed | unknown species raises `UnknownSpecies` (400) | test_integrity |
| 15 | **Any player could act as any user_id** | signed-token ownership check on every player endpoint (+ battle sessions by their owner); ON by default (`REQUIRE_AUTH=0` only for local dev) | test_authz (scans the source for unguarded endpoints) |
| 16 | **Client could pick any wild Pokémon + level** (Mewtwo Lv100) | scan results are signed; `/battle/start` accepts only the player's own token | test_integrity |
| 17 | Several battles at once (reward farming) | starting a battle discards the player's older sessions | test_integrity |
| 18 | Race conditions / double submit / double catch / double spend | state-changing requests are serialized per process; finishing a battle pays once | test_integrity (threads) |
| 19 | Rare Candy leveled differently from battle XP | same path; like the games it grants exactly one level of XP | test_integrity |
| 20 | Route fallback invented Pikachu/Pidgeotto/Eevee | unknown route raises (404) | test_integrity |
| 21 | Route data import failure silently lost regions | import failure now fails the deploy | (import-time) |
| 22 | Silent in-memory mode in production | refuses to start on Render/Vercel without Supabase (`ALLOW_MEMORY_MODE=1` to override) | test_integrity |
| 23 | Wins/losses/streak/player XP never updated by PvE | counted at battle end; ELO is PvP-only | test_integrity |
| 24 | Fake abilities (Intimidate = -15% damage, Guts = +20%, Magic Bounce…) | real event layer: Intimidate, Static/Flame Body/Poison Point/Effect Spore/Rough Skin, Drought/Drizzle/Sand Stream/Snow Warning + weather, Swift Swim/Chlorophyll/Sand Rush, Guts, Huge Power, Technician, Adaptability, Thick Fat, Levitate, Shell/Battle Armor, Magic Bounce, Competitive/Defiant, Inner Focus, Rain Dish | test_integrity |
| 25 | Multi-hit / False Swipe / Facade ignored | implemented from the real move data | test_integrity |
| 26 | Logged-in players silently dropped into the offline engine | no local fallback when logged in (explicit "Play offline demo" only) | (UI) |
| 27 | Gym text promised a full heal but skipped critical Pokémon | wording corrected: critical Pokémon still need Nurse Joy | — |
| 28 | Off-theme emoji in battle logs (⚔️ 💥 ❤️) | retro text glyphs (`glyphs.py`) | test_integrity |
| 29 | XP curve impossible (204,800 XP for Lv12->13); bot stats ignored (10/10/50); bot never saved HP | fixed in an earlier round | test_rules |
| 30 | Battle-session saves/deletes/purges failed silently (turn "succeeded", next request found nothing) | `SupabaseSessionStore` save/load/delete/purge raise `DatabaseError` (503); deletes retry; a read error is no longer "no active battle" | test_persistence |
| 31 | Failed player load could create a replacement player | `load_player` returns `None` ONLY for a positive "no such row"; network/HTTP/JSON/deserialisation failures raise; bootstrap save is checked | test_persistence |
| 32 | Ability changed when a Pokémon was reloaded | ability re-resolved from the restored persistent id in `from_dict` and after evolving | test_persistence |
| 33 | Player + Pokémon saves not atomic | one transaction via the `save_player_atomic` Postgres function (schema.sql); all-or-nothing | test_persistence (fake models the transaction) |
| 34 | Missing `story`/`avatar` column silently dropped journey/avatar data | save fails closed (`SchemaError`); `/api/diagnose` also checks the `version` column and the function | test_persistence, test_db |
| 35 | Website and Telegram could overwrite each other | optimistic `version` check inside the transaction; loser gets `ConcurrentUpdateError` -> HTTP 409 / a clear bot message; nothing written | test_persistence |
| 36 | Bot swallowed failed saves | `save_player` re-raises; global `on_error` tells the player the action was NOT saved | test_bot* |
| 37 | HP formula used `+ level + 5` | `+ level + 10`; Shedinja = 1 | test_persistence |
| 38 | Level-up was a full heal and cleared status | level-up raises current HP by the max-HP gain only; no revive, no status cure | test_persistence |
| 39 | PvP/trade stores reported success on failed writes; read errors looked like "no such match" | `DocStore` save/load/list/delete raise `DatabaseError` | test_persistence |
| 40 | Level-up move learning not wired | free slot -> learned; full moveset -> `pending_moves` (persisted) + `POST /api/party/learn-move`; responses carry `moves_learned` / `move_learning` | test_move_learning |
| 41 | Voluntary switch was free | switching costs the turn: the opponent gets a free hit (shared `_after_turn` finish logic) | test_switch |
| 42 | Catch formula / ball modifiers were placeholders; Telegram catch called the formula with the wrong arguments | Gen 5+ formula with real status multipliers; every ball uses its real condition (unknown condition = no bonus); Quick/Timer use real turn counts; the bot uses the same call | test_catch |
| 43 | Many abilities were flavour only | +25 real effects: Speed Boost, Moxie, Flash Fire (immunity + boost), status immunities, Clear Body / White Smoke / Hyper Cutter, Poison Heal, Magic Guard, Overcoat, Tinted Lens, Solid Rock, Marvel Scale, Fur Coat, Heatproof, Rock Head, Reckless, Lightning Rod / Storm Drain / Sap Sipper / Motor Drive / Dry Skin, Swarm; Power Spot no longer fakes a boost | test_abilities_more |
| 44 | Player `referral_code` regenerated and `created_date` overwritten on every save | restored on load | test_persistence |
| 45 | Tests only ran from one developer's folder | paths resolve from the file location; `python3 tests/run_all.py` runs everything | run_all |
| 46 | Battle/catch "completed" marker was written BEFORE the player save, so a failed save + retry replayed a success that was never stored (no rewards / no Pokémon) | marker is only written AFTER a successful save, and only when the session can't be deleted; `_close_session` never turns a saved result into an error; retries replay the stored answer (no 2nd payout / duplicate Pokémon) | test_idempotency |
| 47 | `in_battle()` guessed "not in battle" on a database error | raises `DatabaseError` (callers return 503) | test_persistence |
| 48 | Pokédex "caught" lost a species once it evolved / was traded / released (nothing ever wrote the history) | `story["caught"]` history recorded on catch, team add, evolve (both forms) and trade; no migration | test_idempotency |
| 49 | Pokédex screen only knew the ~150-species local list | `GET /api/player/{id}/pokedex` returns every server species with seen/caught/owned; the screen uses it (local list = fallback) | test_idempotency (frontend not built here) |
| 50 | 5 species had no verified capture rate (Flabébé, Frillish, Jellicent, Pyroar, Mimikyu) | rates added; `validate_capture_rates()` passes and is a test | test_idempotency |
| 51 | Evolution kept only the old moves | evolved form also fills FREE slots with its latest level-up moves; never overwrites | test_idempotency |
| 52 | No way to move Pokémon between team and box | `GET /api/player/{id}/storage`, `POST /api/storage/deposit|withdraw` (6-limit, last-Pokémon and in-battle guards, resting Pokémon via care) + client functions | test_storage |
| 53 | Dive / Dusk Ball never got their bonus | route terrain flags (keyword heuristic on the route id) are stored with the battle and passed to the catch formula | test_catch |
| 54 | Trade settlement spanned separate saves + rollback writes (could duplicate/lose assets) | `save_players_atomic(p_batch, p_trade)`: both players, all their Pokémon and the trade record in ONE transaction, every row version-checked; no rollback writes; PvP results use it too | test_trade_atomic |
| 55 | **Trading bug (found by the strict checks):** `_take_pokemon` removed a traded Pokémon from the team but left it in the sender's collection, so the sender's next save re-claimed the row the receiver had just been given | removed from every list | test_trade_atomic |
| 56 | A team referencing a missing Pokémon row loaded as a smaller team | raises `DatabaseError` | test_trade_atomic |
| 57 | `ALLOW_LEGACY_SAVE` could restore non-atomic saves in production | ignored when RENDER / VERCEL / PRODUCTION is set | test_trade_atomic |
| 58 | `get_leaderboard` / `get_stats` hid outages as empty results; unused `save_pokemon` was a second write path | raise `DatabaseError`; `save_pokemon` removed; `get_stats` counts correctly | test_trade_atomic |
| 59 | `/health` was the only check | `/api/ready` = bounded read-only DB query + data check (503 when degraded); `/api/diagnose` also checks `save_players_atomic` and data-file problems | test_startup_data |
| 60 | Missing/corrupt `species.json` silently became `{}` (network fallback) | startup error; optional files degrade with a recorded warning | test_startup_data |
| 61 | A Lv44 Meganium with only Tackle (screenshot): Pokémon saved by older versions never got level-up moves, and final forms' own learnsets are sparse | moves are topped up on load (free slots only, never replaces); starting moves and top-up draw on the whole evolution line | test_move_learning |
| 62 | Scouting showed "no encounters" when the request failed | typed result: a failed request shows a retryable error, an empty area says so | (frontend, not built here) |
| 63 | No storage screen | BOX view (`StorageScreen`) on the storage endpoints; `eslint-config-next` aligned with Next 15 | (frontend, not built here) |
| 64 | Abandoning / replacing / fleeing a battle silently healed the team (battle HP only lived in the session) | the damage is written back onto the real Pokémon on replace, successful Run and `POST /api/battle/abandon`, saved BEFORE the old session is deleted | test_battle_lifecycle |
| 65 | Encounter tokens could start unlimited battles until they expired | every token has a nonce; its id is recorded in the player's saved state (`story.enc_used`, same transaction as the player) and a second use is a 403 | test_battle_lifecycle |
| 66 | Travel / heal / trainer start / party heal / rare candy / learn-move / boss ran during a battle | all refuse with 400 while a battle is open (gym_enter is exempt: it is how the next floor starts and it keeps the old fight's damage) | test_battle_lifecycle |
| 67 | A reset / release / trade-away never deleted the Pokémon rows, so they reappeared on reload | `save_player_atomic` now reconciles: the player's rows that are no longer owned are deleted in the same transaction (needs `schema.sql` re-run; the dev-only legacy save can't do this) | test_battle_lifecycle |
| 68 | Battle item: session was healed before the player save — a failed save gave a free heal | player (item) is saved first, session second | test_battle_lifecycle |
| 69 | Failed catch throws didn't advance the turn (Quick Ball bonus repeated, Timer Ball stuck) | the turn is stored in the session after every throw | test_battle_lifecycle |
| 70 | Telegram login: a database outage was reported as "code expired" | 503 "temporarily unavailable"; the code stays valid | test_battle_lifecycle |
| 71 | A login code could be used by two tabs | confirm is conditional on `user_id is null`; consume is `DELETE … RETURNING`, so exactly one caller gets the row | test_battle_lifecycle |
| 72 | An idle (>10 min) battle stopped blocking but stayed in the database as a zombie | the next guarded action settles it (damage kept, session deleted); finished-but-undeletable sessions no longer count as "in battle" | test_battle_lifecycle |
| 73 | Capture-rate validation only logged a warning | production (RENDER / VERCEL / PRODUCTION) refuses to start; in dev the catch endpoint is disabled (503) | test_battle_lifecycle |
| 74 | A failed scout/engage still navigated to the battle screen | `scanArea` returns `{ok,message}`; Scout and Roster show the error and stay put | (frontend, not built here) |
| 75 | Pokédex silently showed the short local list when the API failed | an explicit notice + Retry; the header says LOCAL LIST | (frontend, not built here) |
| 76 | **Vercel build failed:** `StorageMon extends ServerPokemon` redeclared `condition` as `string`, but it is a `MonCondition` object (`lib/apiClient.ts`) | `StorageMon` is now an alias of `ServerPokemon`; the storage screen shows `condition.label` (it would otherwise have printed `[object Object]`) | typechecked with a temp tsconfig (no `node_modules` here) |
| 77 | Six equal-weight dock items (Roster, Dex, Box, Shop, Profile, Config) | dock = JOURNEY / POKÉMON / SHOP; Profile + Settings moved to a top-bar menu | (UI, not built here) |
| 78 | Team, storage and Pokédex lived in three unrelated places | one POKÉMON screen with Team / Storage / Pokédex tabs (`PokemonHub`); older `pokedex` / `storage` navigation still lands on the right tab | (UI) |
| 79 | Journey screen duplicated the dock (Pokédex / Shop / Settings tiles) and a stats box | removed; heading is "Journey", "n / 6 in your team" | (UI) |
| 80 | A scanline overlay still ran although the stylesheet says "no scanlines" | overlay removed; box glow softened | (UI) |
| 81 | Battle screen: the move list took ~45% of a phone screen and pushed your own Pokémon card off-screen | moves/bag/switch are 2-column compact grids (max 34vh, empty move slots hidden on phones), thinner outlines, no bezel effects, safe-area padding; both combatant cards use a compact `StatCard` (smaller portrait, no hunger row / bolt corners / inset shadows) and the log is shorter | (UI, not built here) |
| 82 | Journey screen had no at-a-glance party | six fixed party slots (sprite, level, HP bar, empty = dashed) at the top of the screen; tap to inspect | (UI) |
| 83 | Journey screen was one long stack of equally heavy boxes | thin outlines for ordinary panels, strong outline only for the primary action / selection; order = party → journey → boss → gym; Care Center and Duels & Trades fold away | (UI) |
| 84 | `StatCard` drew a decorative placeholder shield badge on every card | removed | (UI) |
| 85 | Shop / Profile / Settings / Care / Duels / Scout / Storage / Auth / Starter still used heavy 2px outlines and wide letter-spacing | thin outlines for ordinary panels (strong ones kept for selection, alerts and primary actions), calmer tracking | (UI, not rendered here) |
| 86 | Using an item in battle was free (no opponent turn) | item heals, then the opponent acts via the engine's one-sided turn; if that turn ends the fight the normal finish path runs (rewards/loss, one save, session closed) | test_free_turns |
| 87 | A failed escape was free | the opponent attacks (and can win); the answer carries a `turn` result | test_free_turns |
| 88 | **Frontend ignored a fight that ended on a switch / item / failed escape** (the free hit could faint your Pokémon server-side while the screen carried on) | one shared `applyTurnResult` handles move, switch, item and failed-escape results, so defeat/victory screens show up the same way | (frontend, not built here) |
| 89 | Re-entering the gym during an open fight reset the opponent to full HP | the open fight on that floor is resumed (same battle id, opponent keeps its damage) | test_free_turns |
| 90 | Leaderboard hid database outages as an empty ranking | 503 | test_hardening |
| 91 | Auth signing fell back to a public default secret if neither AUTH_SECRET nor SUPABASE_KEY was set | production refuses to sign tokens in that case (a derived-from-SUPABASE_KEY secret keeps working, as before) | test_hardening |
| 92 | A failed Poké Ball throw gave the wild Pokémon no move (unlimited free throws) | a failed throw is a full turn: ball spent and saved first, then the opponent acts via the engine (and can win); the frontend applies that result | test_free_turns |
| 93 | Trade offer / lock / confirm didn't check whether the trainers were in battle (confirm checked only the requester) | offer + lock refuse during a battle; confirm also refuses when the OTHER trainer is in one; a battle that starts later bumps the player row, so the settlement's version check rejects it | test_free_turns |
| 94 | `add_ev` accepted negative / non-integer amounts and could pass 510 | rejects non-positive / bool / float; trims to the 252 per-stat and 510 total caps | test_hardening |
| 95 | No way to report a bug | Settings has a bug-shaped "Report a bug" bubble: `POST /api/feedback` (works logged out, capped input, whitelisted context, 5/hour per sender, admins get a Telegram ping), `GET /api/admin/feedback`, new `feedback` table | test_feedback |
| 96 | Web guest and Telegram player were two different people; no Mini App identity | Mini App sign-in from Telegram's SIGNED initData (`POST /api/auth/telegram/webapp`, HMAC-checked against the bot token, 24h freshness); account linking: Settings → Link Telegram → `/link CODE` in the bot, one database function (`link_identity`) does all checks/archiving atomically; the bot resolves every Telegram id to the player it plays as; retired ids' old tokens get 401 instead of a ghost player; notifications follow the link | test_identity |
| 97 | Both accounts have Pokémon when linking | the bot refuses until the player picks `keep web` / `keep telegram`; the other side is ARCHIVED under a negative id, never deleted | test_identity |

## Open (not done)

| Item | Note |
|---|---|
| Journeys for Johto … Paldea | only Kanto has a full map/gyms/League; unlocking Johto after the Champion drops you into free-roam |
| Many abilities are still flavour only | ~60 have real battle effects; the rest show their real name + description but do nothing yet |
| Storage-box UI | the API returns your stored Pokémon; there is no deposit/withdraw screen yet (only the Care Center's "sleep in ball") |
| Full Pokédex screen (985 species) | server sync works; the screen still lists the small local set |
| Move-learning screen (web + Telegram), storage box on Telegram, held items, weather moves | the server + `learnMove` exist; the web BOX screen exists but is unbuilt/untested here |
| Telegram duel / trade **screens** | invites + accept/decline work in Telegram; fighting and the trade table are on the website (log in with Continue with Telegram) |
| Until Then-style dialogue system (bubbles, lexicon words, story flags, bonds, narrative stats) | NOT built — only the cutscenes and the evolution scene exist |
| Bot menus/panels still use some colourful emoji | battle logs are retro-glyph now |
| Fishing, rival scenes, route trainers, learning AI | not built |
| Multi-worker safety (partial) | DB-level versioning now stops lost updates between processes, but the per-process lock still serialises requests inside one worker; a conflict returns 409 and the client must retry |
| Catch formula | Gen 5+ formula without critical captures; Dive/Dusk use a keyword heuristic for water/cave routes and ignore time of day |
| Deploy needs the new schema | run `database/schema.sql` (adds `players.version`, `pokemon.pending_moves`, `save_player_atomic()`); until then saves fail with a clear `SchemaError` (`ALLOW_LEGACY_SAVE=1` = temporary non-atomic fallback). Never verified against a real Postgres/Supabase here |
| Marketplace / auctions | not started (direct trades exist in the API) |
| Species without a learnset | the same 5 species added for capture rates have no level-up learnset in the data, so they fall back to generic moves |
| No lockfile | `package-lock.json` can't be generated offline: run `npm install` once and commit it; then `npm run build` |
| UI follow-ups | none of the layout work (#76–#85) has been rendered in a browser or at real phone sizes: build it, then send screenshots of Journey, Battle, Pokémon and Shop for spacing tweaks |
| Journey (step 2) | only Kanto has a campaign; the other eight regions need maps, routes, trainers, rivals, gyms, Elite Four and Champion |
| Battle correctness (step 3) | real PP isn't tracked on the server; no full mechanics regression suite yet |
| Learning AI (step 6) | not started: needs a recorded-battle pipeline, a policy that updates and persists, and a held-out evaluation |
| Telegram Mini App setup | set the bot's Mini App / menu button URL in @BotFather to the web app, and set BOT_TOKEN on the API too (it verifies initData with it) |
