# Changes

## Roadmap §3: data audit and first regression slice

- **Species key bug (Flabébé).** The generator folded accents by dropping them, so Flabébé was stored as `flabb`. Its
  learnset, abilities and the Floette evolution were attached to `flabebe`, so the Kalos encounters and the evolution
  rule could miss them. Fixed in `tools/build_data.py` (`slug()` now folds accents: `Flabébé -> flabebe`), and the
  committed `species.json`, `species_extra.json`, `evolutions.json` and `region_kalos.py` were renamed to match.
- **Legacy saves keep loading.** `species_data._ALIASES` maps `flabb -> flabebe`; `PokemonInstance` canonicalizes
  saved names, so existing Flabébé rows still resolve.
- **`tools/audit_species.py`.** Reads the real game tables (wild routes, trainer teams, gyms, Elite Four, rivals) and
  reports species the game needs that the offline data lacks, legacy keys, missing capture rates and missing
  abilities/learnsets. Exits non-zero on errors.
- **Tests.** `test_species_audit.py` (the audit must stay error-free, plus the rename and legacy-load guards) and
  `test_damage_known_values.py` (14 hand-computed damage cases: STAB, type, immunity, burn, crit, stages, Huge Power,
  Thick Fat, level scaling, roll range).

Known data gaps (reported, not fixed): Frillish and Pyroar have no abilities or learnsets in the source dump;
Jellicent and Mimikyu have none either. Aegislash, Meowstic, Pumpkaboo and Gourgeist exist in the committed
`species.json` but the PokeDex source only lists them as forms, so `tools/build_data.py` would drop them on a
rebuild. Do not regenerate `species.json` until that generator gap is fixed.

## Roadmap §3F: held items (Leftovers, Life Orb, Focus Sash)

- **Rules** in `api/_lib/held_items.py` (pure functions, one place): Leftovers heals 1/16 max HP at the end of each
  turn; Life Orb deals +30% from damaging moves and costs the holder 1/10 max HP once per turn it lands a hit; Focus
  Sash saves a full-HP holder from one knock-out hit with 1 HP and is used up.
- **Battle**: `calc_damage` applies the Life Orb multiplier; `_act` applies the Sash and the Life Orb recoil;
  `_end_of_turn` applies Leftovers. `Combatant.save()` writes the item state back, so a used-up Sash stays used.
- **Persistence**: `pokemon.held_item` (new column, see `database/schema.sql`). The session sync restores a used-up
  Sash as used, not as held. **Run `database/schema.sql` before deploying**, or saves fail closed (diagnose reports it).
- **API**: `POST /api/held/equip` and `/api/held/unequip` (refused during a battle). Held items are in the shop
  (prices 1500 / 2500 / 1200 are a tuning choice). `serialize_pokemon` includes `held_item`.
- **Not done**: Choice Band/Specs/Scarf (needs move-lock tracking in battle), the web UI for equipping, and the
  Life Orb rule "recoil also applies on the turn it knocks out" (kept as implemented; check against the games).

## Roadmap §3F: TMs, deliberately not built yet

The PokeDex `Machines` entries merge several generations into one entry (e.g. TM001 lists eight moves), so a
TM-to-move table can't be derived from it, and there is no per-species TM compatibility data at all. Building TM
items on this data would invent game content. Needed before TMs: a verified one-move-per-TM table and TM
compatibility lists per species. Quests (roadmap §3F) are also not started.

## Roadmap §3F: Choice items (Band, Specs, Scarf)

- **Boost**: Choice Band x1.5 Attack, Choice Specs x1.5 Sp. Atk, Choice Scarf x1.5 Speed (`held_items.stat_multiplier`,
  applied in `Combatant.stat`, so damage and turn order both use it).
- **Lock**: the first move a holder uses is recorded as its Choice lock (`bt["cl"]`, battle state only). While locked
  it is offered as the only move. The lock ends when the holder switches out. `battle_move` answers a different move
  with a clear 400 message.
- **Known simplification**: if the locked move runs out of PP, the lock lifts. The games leave the Pokémon with
  Struggle instead. Change `BattleSystem._choice_filter` if that rule is wanted.
- Prices (2000 each) are placeholders. Earlier note saying Choice items were not done is superseded by this section.

## Audit pass (poshow-v16)

- **Random encounter path closed** (audit 1.5). A bare `/api/battle/start` is refused with 400; every wild battle needs a
  scouted, signed token. The web app and bot never used the bare path (checked). Tests were moved to the scout flow
  through `start_wild()` in `tests/harness.py`.
- **Token replay pinned** by test (audit 1.2).
- **Production AUTH_SECRET** shorter than 16 characters now refuses to start (audit 2.5). Previously it only warned.
- Full status of every flagged issue: `docs/AUDIT.md`.

## Quests, route rewards, event engine, marketplace, balance runner

- **Event engine** (`api/_lib/event_engine.py`): game events (catch, win, evolve, visit) update quest progress. Hooks in
  `battle_catch`, `_after_turn` (wins), `evolution.evolve`, `journey_travel`. Engine errors are logged and never break
  a battle or catch. Quest progress and claimed rewards live in `player.story` (no schema change).
- **Quests**: six quests, `GET /api/quests`, `POST /api/quests/claim` (claim once). Daily quests reset each UTC day.
  Reward amounts are placeholders.
- **Route rewards**: first visit to a route pays coins scaled by the route's level. Reported in the travel response.
- **Marketplace** (`market_system.py`): fixed-price Pokémon listings. The Pokémon is escrowed on listing, and buying
  or cancelling is one transaction with the players and the listing (`persist_players`). Fee 5%, expiry three days,
  at most ten listings per player. Endpoints: `/api/market/listings` (public), `/api/market/mine`, `/api/market/list`,
  `/api/market/buy`, `/api/market/cancel`. Refused during battles.
  - **Schema**: new table `market_listings` and a guarded update in `save_players_atomic`: a sold or cancelled listing
    can only change while it is active, so a second buyer is refused in the database. This is covered by the
    emulation only; run `schema.sql` on a real project before relying on it.
  - **Bug found and fixed by the test**: the buyer column was read from the wrong key in the SQL and the emulation.
  - **Authorization**: the public browse endpoint no longer accepts a user id (caught by the authorization audit).
- **Balance runner** (`tools/balance_sim.py`): headless battles, win rate by level offset with 95% intervals,
  seed-replayable. Measurement only; it changes no game data. It is also step 1 of the learning AI.


## UI for the new features, and the learning AI

- **Frontend**: `HeldItemControl` (hold / take back, on each team Pokémon), `QuestsScreen`, `MarketScreen` (browse,
  my listings, sell). Two new dock entries (QUESTS, MARKET). Client functions for each endpoint in `lib/apiClient.ts`.
  Type check: zero errors. Production build: passes with the Google font imports stubbed (see AUDIT 3.5).
- **Learned battle AI**: `api/_lib/learned_ai.py` (observable features, linear and one-hidden-layer policies, save and
  load with architecture checks), `tools/train_learned_ai.py` (evolution-strategy training, paired held-out gate,
  developer recording). The engine hook `BattleSystem.opponent_policy` defaults to None, so battles are unchanged.
  **No weights are shipped:** no policy beat the rule-based AI on held-out matchups. See `docs/AI_REPORT.md`.
- **Balance runner fixes**: the player was scored from the opponent's side, and trainer matchups did not set
  `smart`. Earlier numbers from `balance_sim` are superseded by the corrected report.
