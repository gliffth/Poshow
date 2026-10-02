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
  story jsonb default '{}'
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
  is_shiny boolean default false
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
alter table pokemon add column if not exists trainer_id bigint;
alter table pokemon add column if not exists is_fainted boolean default false;
alter table pokemon add column if not exists is_shiny boolean default false;

-- Temporary battle state. Rebuilt every time because the older schema used different columns
-- and nothing here is worth keeping (an unfinished fight just ends).
drop table if exists battle_sessions cascade;
create table battle_sessions (
  battle_id text primary key,
  user_id bigint not null,
  player_pokemon jsonb not null,
  wild_pokemon jsonb not null,
  updated_at timestamptz default now()
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
  expires_at bigint not null
);

-- If Supabase shows "RLS enabled" on these tables, either switch the API to the service_role key
-- (recommended — it is a SECRET, only ever put it in Render's environment) or disable RLS:
--   alter table players disable row level security;  (repeat for the other tables)
