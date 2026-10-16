-- ════════════════════════════════════════════════════════════════════════════
-- POSHOW — database schema (Supabase / Postgres)         SAFE TO RE-RUN
--
-- This is the ONE schema that matches the code. It never drops anything.
-- Paste the whole file into Supabase → SQL Editor → Run.
-- Then open  https://<your-render-app>.onrender.com/api/diagnose  — it should say "ok": true.
--
-- Already created tables from an older/other schema file? Running this is still fine:
-- it adds whatever is missing and rebuilds `battle_sessions` (temporary data only).
-- ════════════════════════════════════════════════════════════════════════════

create table if not exists players (
  user_id bigint primary key,
  username text not null default 'OPERATOR',
  created_date text,
  level int default 1,
  experience int default 0,
  coins int default 0,
  wins int default 0,
  losses int default 0,
  elo int default 1000,
  current_streak int default 0,
  current_region text default 'kanto',
  regions_unlocked jsonb default '["kanto"]',
  pokemon_caught int default 0,
  pokedex_seen jsonb default '[]',
  inventory jsonb default '{}',
  pokeballs jsonb default '{}',
  login_streak int default 1,
  badges jsonb default '[]',
  achievements jsonb default '[]',
  referral_code text,
  successful_referrals int default 0,
  active_team jsonb default '[]',
  avatar text,
  story jsonb default '{}',
  version integer not null default 0
);

create table if not exists pokemon (
  id text primary key,
  player_id bigint references players(user_id) on delete cascade,
  species_name text not null,
  nickname text,
  level int default 1,
  trainer_id bigint,
  current_hp int,
  max_hp int,
  experience int default 0,
  iv jsonb default '{}',
  ev jsonb default '{}',
  nature text default 'Neutral',
  moves jsonb default '[]',
  status text,
  is_fainted boolean default false,
  is_shiny boolean default false,
  pending_moves jsonb default '[]'
);
create index if not exists idx_pokemon_player on pokemon(player_id);

-- ── bring tables created from an older schema up to date (no-ops if already correct) ──
alter table players add column if not exists created_date text;
alter table players add column if not exists active_team jsonb default '[]';
alter table players add column if not exists referral_code text;
alter table players add column if not exists successful_referrals int default 0;
alter table players add column if not exists login_streak int default 1;
alter table players add column if not exists badges jsonb default '[]';
alter table players add column if not exists achievements jsonb default '[]';
alter table players add column if not exists avatar text;
alter table players add column if not exists story jsonb default '{}';
alter table players add column if not exists version integer not null default 0;   -- optimistic lock (see save_player_atomic)
alter table pokemon add column if not exists trainer_id bigint;
alter table pokemon add column if not exists is_fainted boolean default false;
alter table pokemon add column if not exists is_shiny boolean default false;
alter table pokemon add column if not exists pending_moves jsonb default '[]';

-- ── ATOMIC player save (one transaction) + optimistic version check ──────────────────────────────────────
-- The API and the Telegram bot call this through PostgREST (POST /rest/v1/rpc/save_player_atomic).
--   * the players row and ALL pokemon rows are written together, or not at all
--   * p_expected_version must equal the row's current `version` (NULL = "this player is new"); otherwise the
--     function raises 'version_conflict' and nothing is written, so the website and Telegram can't clobber each
--     other with stale copies
--   * a key in p_player that is not a real players column makes the whole call fail (no silent column dropping)
-- Returns the new version.
create or replace function public._save_player_core(p_player jsonb, p_pokemon jsonb, p_expected_version integer)
returns integer
language plpgsql
as $fn$
declare
  v_uid bigint := (p_player->>'user_id')::bigint;
  v_cur integer;
  v_new integer;
  v_key text;
begin
  if v_uid is null then
    raise exception 'missing_user_id';
  end if;

  select version into v_cur from public.players where user_id = v_uid for update;

  if not found then
    if p_expected_version is not null then
      raise exception 'version_conflict: player % no longer exists (expected version %)', v_uid, p_expected_version;
    end if;
    insert into public.players
      select (jsonb_populate_record(null::public.players, p_player || jsonb_build_object('version', 1))).*;
    v_new := 1;
  else
    if p_expected_version is null or p_expected_version <> v_cur then
      raise exception 'version_conflict: expected version %, database has %', p_expected_version, v_cur;
    end if;
    for v_key in select jsonb_object_keys(p_player) loop
      continue when v_key in ('user_id', 'version');
      execute format(
        'update public.players set %1$I = (jsonb_populate_record(null::public.players, $1)).%1$I where user_id = $2',
        v_key) using p_player, v_uid;
    end loop;
    v_new := v_cur + 1;
    update public.players set version = v_new where user_id = v_uid;
  end if;

  if p_pokemon is not null and jsonb_typeof(p_pokemon) = 'array' then
    -- RECONCILE: this player's Pokémon rows that are no longer in what they own (admin reset, released, traded away)
    -- are removed, so they can't reappear on the next load. A row now owned by someone else is not touched.
    delete from public.pokemon
     where player_id = v_uid
       and id not in (select e->>'id' from jsonb_array_elements(p_pokemon) e);
  end if;

  if p_pokemon is not null and jsonb_typeof(p_pokemon) = 'array' and jsonb_array_length(p_pokemon) > 0 then
    insert into public.pokemon
      (id, player_id, species_name, nickname, level, trainer_id, current_hp, max_hp, experience,
       iv, ev, nature, moves, status, is_fainted, is_shiny, pending_moves)
    select r.id, r.player_id, r.species_name, r.nickname, r.level, r.trainer_id, r.current_hp, r.max_hp, r.experience,
           r.iv, r.ev, r.nature, r.moves, r.status, r.is_fainted, r.is_shiny, coalesce(r.pending_moves, '[]'::jsonb)
      from jsonb_populate_recordset(null::public.pokemon, p_pokemon) r
    on conflict (id) do update set
      player_id = excluded.player_id, species_name = excluded.species_name, nickname = excluded.nickname,
      level = excluded.level, trainer_id = excluded.trainer_id, current_hp = excluded.current_hp,
      max_hp = excluded.max_hp, experience = excluded.experience, iv = excluded.iv, ev = excluded.ev,
      nature = excluded.nature, moves = excluded.moves, status = excluded.status,
      is_fainted = excluded.is_fainted, is_shiny = excluded.is_shiny, pending_moves = excluded.pending_moves;
  end if;

  return v_new;
end
$fn$;

-- Single-player entry point (what every normal save calls).
create or replace function public.save_player_atomic(p_player jsonb, p_pokemon jsonb, p_expected_version integer)
returns integer
language sql
as $fn$
  select public._save_player_core(p_player, p_pokemon, p_expected_version);
$fn$;

-- Several players in ONE transaction (trade settlement). p_batch = [{"player":{..}, "pokemon":[..], "expected_version":n}, ...]
-- Every row is version-checked and all are written, or none are. An optional p_trade row (the trades table) is
-- written in the same transaction. Rows are processed in user_id order so two
-- simultaneous settlements can't deadlock. Returns {"<user_id>": new_version, ...}.
create or replace function public.save_players_atomic(p_batch jsonb, p_trade jsonb default null)
returns jsonb
language plpgsql
as $fn$
declare
  v_item jsonb;
  v_out jsonb := '{}'::jsonb;
  v_ver integer;
begin
  if p_batch is null or jsonb_typeof(p_batch) <> 'array' or jsonb_array_length(p_batch) = 0 then
    raise exception 'empty_batch';
  end if;
  for v_item in
    select value from jsonb_array_elements(p_batch) order by (value->'player'->>'user_id')::bigint
  loop
    v_ver := public._save_player_core(v_item->'player', v_item->'pokemon',
                                      nullif(v_item->>'expected_version', '')::integer);
    v_out := v_out || jsonb_build_object(v_item->'player'->>'user_id', v_ver);
  end loop;
  -- the trade record is completed in the SAME transaction as both players' new state
  if p_trade is not null then
    insert into public.trades
      select (jsonb_populate_record(null::public.trades, p_trade)).*
    on conflict (id) do update set status = excluded.status, state = excluded.state, ts = excluded.ts;
  end if;
  return v_out;
end
$fn$;

-- Temporary battle state. Rebuilt every time because the older schema used different columns
-- and nothing here is worth keeping (an unfinished fight just ends).
drop table if exists battle_sessions cascade;
create table battle_sessions (
  battle_id text primary key,
  user_id bigint not null,
  player_pokemon jsonb not null,
  wild_pokemon jsonb not null,
  updated_at timestamptz default now(),
  completed_at timestamptz,                -- set (after the player was saved) when a finished session could not be deleted
  completion_result jsonb                  -- the answer to replay if the client retries that request
);

-- ── web accounts (username + password) ──
create table if not exists accounts (
  username text not null,
  username_lower text primary key,
  password_hash text not null,
  user_id bigint not null unique,
  created_at timestamptz default now()
);

-- ── one-time codes for "Continue with Telegram" ──
create table if not exists login_codes (
  code text primary key,
  user_id bigint,
  username text,
  expires_at bigint not null,
  link_user_id bigint                  -- set on a "link my Telegram" code: the web player that asked for it
);
alter table login_codes add column if not exists link_user_id bigint;

-- ── PvP duels and player-to-player trades (shared JSON documents) ──
create table if not exists pvp_matches (
  id text primary key,
  user_a bigint not null,
  user_b bigint not null,
  status text not null,
  state jsonb not null default '{}',
  ts bigint not null
);
create index if not exists idx_pvp_a on pvp_matches(user_a);
create index if not exists idx_pvp_b on pvp_matches(user_b);

create table if not exists trades (
  id text primary key,
  user_a bigint not null,
  user_b bigint not null,
  status text not null,
  state jsonb not null default '{}',
  ts bigint not null
);
create index if not exists idx_trades_a on trades(user_a);
create index if not exists idx_trades_b on trades(user_b);

-- ── admin-set image overrides for scenes ──
create table if not exists site_assets (
  key text primary key,
  url text not null,
  updated_at timestamptz default now()
);

-- If Supabase shows "RLS enabled" on these tables, either switch the API to the service_role key
-- (recommended — it is a SECRET, only ever put it in Render's environment) or disable RLS:
--   alter table players disable row level security;  (repeat for the other tables, incl. site_assets)
alter table battle_sessions add column if not exists completed_at timestamptz;
alter table battle_sessions add column if not exists completion_result jsonb;

-- ── player feedback / bug reports (Settings -> Report a bug) ──
create table if not exists feedback (
  id bigserial primary key,
  user_id bigint,
  username text,
  category text not null default 'bug',
  message text not null,
  context jsonb default '{}',
  status text not null default 'new',
  created_at timestamptz default now()
);

-- ── one player across web and Telegram ──
-- alias_id plays as user_id. kind 'telegram' = a Telegram account that plays as a web player;
-- kind 'web' = a retired web id that now redirects to the Telegram player. Old tokens for an alias are refused.
create table if not exists identity_links (
  alias_id bigint primary key,
  user_id bigint not null,
  kind text not null default 'telegram',
  created_at timestamptz default now()
);

-- Link a Telegram account to the web account that asked for `p_code`, atomically.
--   neither side has Pokémon, or only the web side does  -> the web player stays; Telegram plays as it
--   only the Telegram side has Pokémon                    -> the Telegram player stays; the web login now points at it
--   BOTH have Pokémon                                     -> 'conflict' until p_keep = 'web' or 'telegram' is given;
--                                                            the other side is ARCHIVED under a negative id, never deleted
-- Returns {"status": linked | already_linked | conflict | expired | linked_elsewhere | not_a_link_code | already_used | web_account_retired, ...}
create or replace function public.link_identity(p_code text, p_telegram_id bigint, p_tg_name text, p_keep text default null)
returns jsonb
language plpgsql
as $fn$
declare
  c record;
  w bigint;
  t bigint := p_telegram_id;
  existing bigint;
  w_prog boolean;
  t_prog boolean;
  canonical bigint;
  web_wins boolean;
  acct_name text;
begin
  select * into c from public.login_codes where code = upper(coalesce(p_code, '')) for update;
  if not found or c.expires_at < extract(epoch from now())::bigint then
    return jsonb_build_object('status', 'expired');
  end if;
  w := c.link_user_id;
  if w is null then return jsonb_build_object('status', 'not_a_link_code'); end if;
  if c.user_id is not null then return jsonb_build_object('status', 'already_used'); end if;

  select user_id into existing from public.identity_links where alias_id = t;
  if found then
    if existing <> w then return jsonb_build_object('status', 'linked_elsewhere'); end if;
    select username into acct_name from public.accounts where user_id = w limit 1;
    update public.login_codes set user_id = w, username = coalesce(acct_name, p_tg_name, 'TRAINER') where code = c.code;
    return jsonb_build_object('status', 'already_linked', 'canonical', w);
  end if;
  if exists (select 1 from public.identity_links where alias_id = w) then
    return jsonb_build_object('status', 'web_account_retired');
  end if;

  w_prog := exists (select 1 from public.pokemon where player_id = w);
  t_prog := exists (select 1 from public.pokemon where player_id = t);
  if w_prog and t_prog and p_keep is null then
    return jsonb_build_object('status', 'conflict');
  end if;
  if p_keep = 'web' then
    web_wins := true;
  elsif p_keep = 'telegram' then
    web_wins := false;
  else
    web_wins := not t_prog;       -- only the Telegram side has Pokémon: it stays; otherwise the web player stays
  end if;

  delete from public.battle_sessions where user_id in (w, t);
  if web_wins then
    update public.pokemon set player_id = -t where player_id = t;
    update public.players set user_id = -t where user_id = t;
    insert into public.identity_links (alias_id, user_id, kind) values (t, w, 'telegram');
    canonical := w;
  else
    update public.pokemon set player_id = -w where player_id = w;
    update public.players set user_id = -w where user_id = w;
    update public.accounts set user_id = t where user_id = w;
    insert into public.identity_links (alias_id, user_id, kind) values (w, t, 'web');
    canonical := t;
  end if;

  select username into acct_name from public.accounts where user_id = canonical limit 1;
  update public.login_codes set user_id = canonical, username = coalesce(acct_name, p_tg_name, 'TRAINER') where code = c.code;
  return jsonb_build_object('status', 'linked', 'canonical', canonical,
                            'kept', case when web_wins then 'web' else 'telegram' end,
                            'username', coalesce(acct_name, p_tg_name, 'TRAINER'));
end
$fn$;
