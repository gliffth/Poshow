# Offline tests

Run the whole suite from a clean checkout, from any directory:

    python3 tests/run_all.py

Each `test_*.py` also runs on its own (`python3 tests/test_catch.py`; `test_db.py` takes `good` or `bad`).
They need no FastAPI, Telegram, Supabase or network (stand-ins in `stubs/` and `fake_supabase.py`, which models
PostgREST *and* the `save_player_atomic()` transaction + version check). Paths resolve from the file location.

They are a safety net, not a substitute for a real deploy: nothing here ran against real FastAPI, Telegram,
Supabase/Postgres or a Next.js build. In particular the SQL function in `database/schema.sql` is only emulated.
