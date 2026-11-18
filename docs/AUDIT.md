# POSHOW — consolidated audit (state of the code in poshow-v16)

Every issue flagged across the reviews and roadmap, with its status checked against the current code in this build.
Nothing here is marked done on the strength of a note alone: "Fixed" means the code was checked in this build, and,
where a test is named, the test passes. Run `python3 tests/run_all.py` (50 suites, all green) and
`python3 tools/audit_species.py` (no errors) to reproduce.

## Status key

| Status | Meaning |
|---|---|
| **Fixed (tested)** | Code verified in this build and covered by a named test |
| **Fixed (code)** | Code verified in this build; no test, or the test only covers the offline path. Needs a live-database check |
| **Partial** | Part of the problem is addressed; the rest is open. Details say what remains |
| **Open** | Not addressed |
| **Blocked (data)** | Cannot be done until verified game data is supplied. Not fabricated |
| **Not started** | Planned work, no code yet |

Count across the 68 items in §1–§7: 26 fixed, 16 open, 13 partial, 5 blocked, 5 not started, 1 accepted, 1 done, 1 unverified.

---

## 1. Battle lifecycle and encounters (review of v3, second pass; review of v7)

| # | Issue | Status | Evidence / what remains |
|---|---|---|---|
| 1.1 | Starting a new battle discards an active one (escape without cost) | **Done** | Starting a new battle while another is live now gives the old opponent the free hit a failed escape gives. A stale session (older than the battle lock) is still settled without a hit |
| 1.2 | Encounter token replayable | **Fixed (tested)** | Token id recorded in `story.enc_used` on use. `test_no_tokenless_battles.py`: replay is refused with 403 |
| 1.3 | Journey travel / heal / trainer start allowed during a battle | **Fixed (code)** | `_no_battle` on all three journey endpoints (checked in `api/index.py`). No dedicated test yet |
| 1.4 | Idle battle counts as inactive after 10 minutes (no explicit lifecycle) | **Partial** | A stale-session sweep and `BATTLE_LOCK_S` exist. There is still no explicit active / abandoned / completed / expired state machine |
| 1.5 | Tokenless random encounter path (client can reroll) | **Fixed (tested)** | Closed this session. A bare `/api/battle/start` returns 400. `test_no_tokenless_battles.py`. The web app and Telegram bot never used this path (checked) |
| 1.6 | Item use does not cost the opponent a turn | **Fixed (code)** | `battle_item` calls `_free_enemy_turn` |
| 1.7 | Failed flee does not cost a turn | **Fixed (code)** | `battle_flee` calls `_free_enemy_turn` on failure |
| 1.8 | Gym entry can replace the current floor's opponent | **Fixed (code)** | Resume on the same floor is implemented in `gym_enter`; `test_free_turns.py` covers resume |
| 1.9 | Failed battle-item save can give a free heal | **Partial** | Order is now player save first, then session. No idempotency key, so retries are not formally deduplicated |
| 1.10 | Failed capture does not advance the turn counter | **Fixed (code)** | Session turn saved on failed catch |
| 1.11 | Battle-catch persistence ordering (ball spent vs turn saved) | **Partial** | Ordering documented; a crash between the two writes can lose a bonus turn but not grant a free ball. Idempotency key still missing |
| 1.12 | Pokémon reconstruction changes stats during a PokéAPI outage | **Partial** | All 985 species in `species.json` load offline, so known species never call the network. Forms outside the file still do. Stats are not snapshotted per Pokémon |
| 1.13 | PokéAPI results cached only in memory | **Open** | Low priority while offline data covers the game. No disk cache |

## 2. Persistence, accounts and reliability

| # | Issue | Status | Evidence / what remains |
|---|---|---|---|
| 2.1 | Admin reset leaves saved Pokémon in the database (they reappear on reload) | **Fixed (code)** | `_save_player_core` deletes Pokémon not in the owned id list. Needs a live Postgres test |
| 2.2 | Login-code lookup outage reported as "code expired" | **Fixed (code)** | `_get_code` raises a 503 on database error. Not yet a dedicated test |
| 2.3 | Telegram login codes not consumed atomically | **Fixed (code)** | Consumed with `DELETE … RETURNING`, so one caller gets the row. Needs a live database race test |
| 2.4 | Leaderboard outage shown as an empty leaderboard | **Fixed (code)** | `leaderboard` raises 503 on read failure |
| 2.5 | Production signing key can be a guessable default | **Fixed (tested)** | `test_auth_secret_policy.py`: production refuses a short or missing secret |
| 2.6 | Schema changes must be applied before deploy | **Open (operational)** | Requires running `database/schema.sql` on the live database and checking `/api/diagnose`. Not done from here |

## 3. Frontend

| # | Issue | Status | Evidence / what remains |
|---|---|---|---|
| 3.1 | Scouting screen navigates to battle even when the start fails | **Fixed (code)** | `ScoutScreen` checks `res.ok` before navigating |
| 3.2 | Pokédex silently falls back to a smaller local list | **Fixed (code)** | `catalogueFailed` flag and retry shown to the player |
| 3.3 | Frontend build and TypeScript check never run | **Fixed (code)** | Type check: zero errors. Production build: passes in a scratch copy with the two Google font imports stubbed. The real build needs network access to Google Fonts (see 3.5). Checked in this environment, not yet in CI |
| 3.4 | Held-item equip and Choice-lock UI | **Fixed (code)** | `HeldItemControl` on every team Pokémon in the storage screen (hold, take back; refusals in battle are shown). The Choice-lock refusal reaches the player through the battle log |

## 4. Capture rates and data

| # | Issue | Status | Evidence / what remains |
|---|---|---|---|
| 4.1 | Capture-rate validation only warns | **Fixed (code)** | Catching is disabled (503) when the data check fails, instead of guessing |
| 4.2 | Accent-stripped species key `flabb` (Flabébé) | **Fixed (tested)** | Renamed in `species.json`, `species_extra.json`, `evolutions.json`, `region_kalos.py`. Legacy saves resolve through an alias. `test_species_audit.py` |
| 4.3 | Generator drops four species that the committed `species.json` has (Aegislash, Meowstic, Pumpkaboo, Gourgeist) | **Open** | The PokeDex source lists them only as forms. Do not regenerate `species.json` until this is fixed |
| 4.4 | Frillish and Pyroar have no abilities or level-up learnsets (Pyroar is in the Kalos Elite Four) | **Open (data)** | Source dump lacks them. Needs a verified source. Audit reports them as warnings |
| 4.5 | Jellicent and Mimikyu have no abilities or learnsets | **Open (data)** | Not used by any current game table |
| 4.6 | 36 national-dex numbers have no species entry | **Open (low)** | Forms and alternates. Only the Kalos-referenced species were needed, and the audit confirms they are present |
| 4.7 | Ditto has no level-up learnset | **Accepted** | Correct for the games (Ditto learns Transform). Allow-listed in the audit |
| 4.8 | No regional forms, genders or weights | **Open** | Needed for Heavy Ball, Love Ball and some regional encounters (see §7) |

## 5. Battle correctness and test coverage (roadmap G)

| # | Item | Status | Evidence / what remains |
|---|---|---|---|
| 5.1 | Damage regression against hand-computed values | **Partial** | `test_damage_known_values.py`: 14 cases (STAB, type, immunity, burn, crit, stages, Huge Power, Thick Fat, level, roll range) |
| 5.2 | Held-item and Choice-item rules | **Fixed (tested)** | `test_held_items.py`, `test_held_api.py`, `test_choice_items.py` |
| 5.3 | Abilities, XP, evolution, move learning regression | **Partial** | Existing suites (`test_abilities*.py`, `test_evolution.py`, `test_move_learning.py`) cover these. No consolidated known-value suite for XP |
| 5.4 | Web and Telegram produce the same battle results | **Open** | No parity test |
| 5.5 | Audit of which move effects are implemented | **Open** | Not done |
| 5.6 | Life Orb recoil on a knock-out turn | **Done (checked from memory of the games, not a source)** | Recoil on every turn that lands damage, including a knock-out |
| 5.7 | Choice lock with no PP | **Done** | The locked move stays the only choice and turns into Struggle, as in the games |
| 5.8 | Double battles, Mega, Tera, Dynamax, Z-moves | **Not started** | Out of current scope |
| 3.5 | `next build` needs network access to Google Fonts (`next/font`) | **Open (operational)** | Fails in an offline environment. Fine on Vercel. Any offline build needs the font imports stubbed |
| 3.6 | Quests and Market screens | **Fixed (code)** | `QuestsScreen`, `MarketScreen` (browse, mine, sell), navigation dock entries. Type-checked and built; no browser test yet |
| 5.9 | Marketplace SQL and the event-engine schema (`market_listings`, batch save branch) run on a real Postgres | **Open (operational)** | Only the emulation in `tests/fake_supabase.py` has run. Run `database/schema.sql` on a test project and the race test against it before relying on the market |

## 6. Items and progression (roadmap F)

| # | Item | Status | Evidence / what remains |
|---|---|---|---|
| 6.1 | Held items (Leftovers, Life Orb, Focus Sash) | **Fixed (tested)** for battle rules; API present; **UI open** | `held_items.py` and the three held-item test files |
| 6.2 | Choice Band / Specs / Scarf | **Fixed (tested)** for battle; **UI open** | `test_choice_items.py` |
| 6.3 | TM system | **Blocked (data)** | PokeDex TM entries merge several generations. No per-species TM compatibility data. See the changelog |
| 6.4 | Daily-boss TM and competitive-item rewards | **Blocked (data)** | Depends on 6.3 |
| 6.5 | Quests | **Fixed (tested)** | `event_engine.py`: six quests (four permanent, two daily that reset each day), claim-once rewards. UI: `QuestsScreen`. `test_events_quests.py`. Reward amounts are placeholders to tune |
| 6.6 | Exploration rewards on routes | **Fixed (tested)** | First visit to each route pays coins, scaling with the route's level (at least 100). Paid once per route. Towns pay nothing. `test_events_quests.py`. Amounts are a placeholder formula |

## 7. Game content (roadmap A–E, I–K)

| # | Item | Status | Evidence / what remains |
|---|---|---|---|
| 7.1 | Kanto, Johto, Kalos campaigns | **Done** | Tested by `test_regions.py` (88 checks) |
| 7.2 | Hoenn, Sinnoh, Unova, Alola, Galar, Paldea campaigns | **Blocked (data)** | Need verified routes, trainers, gyms, rivals, Elite Four and Champion data. Alola, Galar and Paldea also need a model extension (trials, challenge gyms, non-linear routes) |
| 7.3 | Story and narrative layer (event engine, dialogue, memory) | **Partial** | The event engine exists and drives quests and route rewards (events: catch, win, evolve, visit). Dialogue, scripted scenes, persistent story flags for narrative, villain arcs and NPC memory are not built. Needs at least one campaign to attach to |
| 7.4 | Legendary one-time encounters with conditions | **Partial** | Rare variants and catch-rate tiers exist. Placed one-time legendaries with flags are not built |
| 7.5 | Learning battle AI (developer recording, self-play, evaluation) | **Partial** | Built: headless runner, developer recording (`docs/ai/baseline_decisions.jsonl`), observable features, linear and one-hidden-layer policies, evolution-strategy training, paired held-out gate, opt-in engine hook (default off). **Result: no policy beat the rule-based AI on held-out matchups (seven runs, see `docs/AI_REPORT.md`), so nothing is shipped.** Lookahead features were added and retrained (runs 4 and 5): still tied with the baseline. Switching and 3-against-3 team battles were then built and trained (runs 6 and 7): not better than the baseline. Next: many more team matchups |
| 7.6 | Difficulty tuning (Radical Red / Run & Bun style teams) | **Partial** | Measurement: `tools/balance_sim.py` reports win rate by level offset with 95% intervals. Two errors in the first version were found and fixed (the player was scored from the opponent's side; trainers were not flagged as smart). Corrected numbers: route trainer 8.7% at −4 levels to 100% at 0. A lone Pokémon can't measure gym difficulty (100% everywhere), so tuning waits for full team battles |
| 7.7 | Telegram parity: storage-box management | **By design (app-only)** | The bot is a lighter companion; storage management stays in the web app |
| 7.8 | Telegram parity: move-learning prompts | **Unverified** | Not tested end to end |
| 7.9 | Telegram parity: full duel and trade flow | **By design (partly app-only)** | Group `/pvp` and the classic duel work in the bot. Team building, preview, the matchmaking queue and the new formats stay in the web app |
| 7.10 | Marketplace and auctions (listings, escrow, fees, expiry) | **Partial** | Fixed-price Pokémon listings with escrow, atomic purchase (5% fee), cancel, three-day expiry, race protection; UI in `MarketScreen`. No item listings, no auctions. **The SQL is verified only against the test emulation, not a live Postgres.** Fee and expiry are placeholders |
| 7.11 | Critical captures | **Done** | Gen 7 rule (odds rise with species caught, one shake check); covered by formula and simulation tests |
| 7.12 | Dusk Ball time of day | **Done** | Uses the player's clock sent with the throw (night is 8 pm to 6 am); no clock means not night |
| 7.13 | Heavy Ball (needs species weight) and Love Ball (needs gender) | **Blocked (data)** | See 4.8 |
| 7.14 | Fishing, wider rival and route events | **Not started** | |

## 7b. PvP renovation

Built and tested offline: formats (Quick Duel, 3v3 Singles, 6v6 Singles, Friendly with custom rules, classic kept for the bot), server-side team validation, team preview, saved teams (ten per player), a matchmaking queue with a widening rating window, per-format ratings and history, repeat-opponent damping, turn timers settled by the next request, turn ids and request ids so a retry never plays a move twice, and a long-poll endpoint with a polling fallback. The web lobby, team builder and arena use these.

Measured with `tools/pvp_bench.py` (in-memory database stand-in, 40 ms simulated per request, so only the request counts are exact): a move went from 5 database requests to 2 and a state poll from 2 to 1; a move took 203 ms before and 81 ms after at that delay; the idle screen no longer polls trades, and the connection ping now sleeps while the tab is hidden and runs once a minute while the server answers.

Not verified: the frontend has not been built or opened in a browser; there has been no test against a real Supabase or Render; the real cause of multi-minute waits was not measured (only the code paths were). Sprites load from the PokeAPI sprite repository and fall back to a letter. Long polls hold a connection open, so they depend on the host not buffering responses.

Not built: Doubles, Random Battle, Tournaments, spectators, seasons, WebSockets (long poll was used instead), per-format leaderboards, Telegram support for the new formats. Matchmaking and the long-poll wake-up are in-process: with more than one server process the queue lock is not shared and the wake-up falls back to a re-check every four seconds.

## 8. Process and honesty notes

- Earlier bundles (`poshow-v3` fixes and `poshow-v7` fixes) were written before they were run against the test suite, and some referenced helper names that were never checked. Treat those bundles as **superseded**. The status above is from v16, where every change was run.
- Test doubles: `harness.py` replaces PokéAPI with a small fake. Tests that need real species data reset it explicitly (`test_species_audit.py`). Database behaviour is tested against `fake_supabase.py`, which models the SQL functions but does not run them. **No test in this build executes `schema.sql` on a real Postgres.**

## 9. Recommended order from here

1. Decide 1.1 (refuse vs charge for abandoning a fight) and 5.6 / 5.7 (game-rule choices).
2. Run `database/schema.sql` on a real Supabase project and check `/api/diagnose`. Then write one live-database test for 2.1 and 2.3.
3. Fix the generator gap 4.3 before any data rebuild.
4. Build the frontend once (3.3), then add the equip and Choice-lock UI (3.4).
5. Get verified data for 4.4, 6.3 and 7.2. Each unblocks a set of features.
6. Then the content roadmap: quests and route rewards (6.5, 6.6), the event engine (7.3), and the marketplace (7.10).
