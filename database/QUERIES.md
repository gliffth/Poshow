# Useful queries

Run these in the Supabase SQL editor. Replace `123456789` with a player's `user_id`.

```sql
-- Top players
select user_id, username, level, coins, elo, wins, losses, current_region
from players order by elo desc limit 20;

-- A player's Pokémon
select id, species_name, nickname, level, current_hp, max_hp, is_shiny
from pokemon where player_id = 123456789 order by level desc;

-- Players with the most Pokémon
select player_id, count(*) as pokemon from pokemon group by player_id order by pokemon desc limit 20;

-- Open battle sessions
select battle_id, user_id, updated_at, completed_at from battle_sessions order by updated_at desc;

-- Remove sessions idle for a day
delete from battle_sessions where updated_at < now() - interval '1 day';

-- Linked web / Telegram accounts, and players archived by a link (negative ids)
select alias_id, user_id, kind, created_at from identity_links order by created_at desc;
select user_id, username from players where user_id < 0;

-- Recent bug reports and ideas
select id, category, username, left(message, 120) as message, status, created_at
from feedback order by id desc limit 50;

-- Latest trades and duels
select id, user_a, user_b, status, ts from trades order by ts desc limit 20;
select id, user_a, user_b, status, ts from pvp_matches order by ts desc limit 20;
```

## Database health

```sql
select public.db_health();                          -- connections, locks, cache hit ratio, slowest statements
select public.db_explain('load_player', 123456789);  -- execution plan of a named query
```

`db_explain` accepts: `load_player`, `load_pokemon`, `player_sessions`, `trades_for_user`, `duels_for_user`,
`leaderboard`, `account_by_user`, `identity_links`. The same data is available to admins through
`/api/admin/db-health` and `/api/admin/db-explain` (see [../docs/DEPLOY.md](../docs/DEPLOY.md)).
