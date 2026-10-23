# Tests

    python3 tests/run_all.py

Runs every `test_*.py` in its own process (`test_db.py` runs twice, against the current and an old schema).
Each file can also be run on its own, from any directory.

The tests are offline. They use stand-ins instead of FastAPI, Telegram and Supabase (`stubs/`, `fake_supabase.py`).
The fake database models PostgREST, the transactional functions in `database/schema.sql` (saves, version checks,
account linking) and the foreign key from `pokemon` to `players`. The SQL itself is not executed: run
`database/schema.sql` on a real database and check `/api/diagnose` to verify it.

`bench_roundtrips.py` prints the database calls each game action makes. `../tools/db_bench.py` measures latency
against a running API.
