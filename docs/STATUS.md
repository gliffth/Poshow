# Status (verified, not aspirational)

**Offline suite:** `python3 tests/run_all.py` — everything green. That covers logic against fakes only: nothing here ran
against real Supabase/Postgres, FastAPI, Telegram or a Next.js build.

**Before deploying:** re-run `database/schema.sql` (adds `players.version`, `pokemon.pending_moves`,
`battle_sessions.completed_at/completion_result`, and the `save_player_atomic()` + `save_players_atomic()` functions) and confirm `/api/diagnose`
says `"ok": true`. Test `save_player_atomic()` once on the real database — it is only emulated in the tests.

**Works (tested offline):** fail-closed persistence, atomic + versioned saves, retry-safe battle/catch finishing,
Gen 5+ catch formula with ball rules, level-up + evolution move learning, voluntary switch costs a turn, ~60 abilities,
storage box API, full Pokédex catalogue + history.

**Schema:** re-run `database/schema.sql` again — `save_player_atomic` now also deletes Pokémon rows a player no longer owns.

**After deploy:** `/api/ready` must return 200 and `/api/diagnose` must say ok.

**Not done:** move-learning screen, Telegram storage, other eight regional journeys, marketplace, narrative memory,
Telegram duel/trade screens, remaining abilities (description-only), critical captures. See `docs/BUGS.md`.
