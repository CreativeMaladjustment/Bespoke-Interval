-- Schema-only migration for the Bespoke Interval trip planner.
-- All `create table` statements use `if not exists` for safety.
-- Seed data is in a separate data migration (20260830020000_seed_thanksgiving_data.sql).

create extension if not exists pgcrypto;

create table if not exists public.trips (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  home_timezone text not null default 'America/Denver',
  destination_timezone text not null default 'Europe/London',
  pin_hash text not null,
  starts_at timestamptz not null,
  starts_terminal text,
  ends_at timestamptz not null,
  ends_terminal text,
  created_at timestamptz not null default now()
);

alter table public.trips enable row level security;

create table if not exists public.travelers (
  id uuid primary key default gen_random_uuid(),
  trip_id uuid not null references public.trips(id) on delete cascade,
  name text not null,
  initial text not null,
  role text not null,
  sort_order int not null default 0
);

alter table public.travelers enable row level security;

create table if not exists public.trip_days (
  id uuid primary key default gen_random_uuid(),
  trip_id uuid not null references public.trips(id) on delete cascade,
  day_index int not null,
  calendar_date date not null,
  reference_timezone text not null,
  kicker text,
  tag text,
  unique (trip_id, day_index)
);

alter table public.trip_days enable row level security;

create table if not exists public.blocks (
  id uuid primary key default gen_random_uuid(),
  trip_id uuid not null references public.trips(id) on delete cascade,
  trip_day_id uuid not null references public.trip_days(id) on delete cascade,
  type text not null check (type in
    ('travel','transit','theatre','meal','walk','museum','library','tourist','rest')),
  title text not null,
  subtitle text,
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  who text not null default 'Both' check (who in ('jd','emy','Both')),
  location text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (ends_at > starts_at)
);

create index if not exists blocks_trip_day_idx on public.blocks(trip_day_id);
create index if not exists blocks_trip_starts_idx on public.blocks(trip_id, starts_at);

alter table public.blocks enable row level security;

create table if not exists public.tickets (
  id uuid primary key default gen_random_uuid(),
  trip_id uuid not null references public.trips(id) on delete cascade,
  category text not null check (category in
    ('travel','transit','theatre','meal','walk','museum','library','tourist','rest')),
  kind text not null,
  title text not null,
  venue text,
  occurs_at timestamptz,
  who text not null default 'Both' check (who in ('jd','emy','Both')),
  facts jsonb not null default '[]'::jsonb,
  sort_order int not null default 0
);

alter table public.tickets enable row level security;

create table if not exists public.flights (
  id uuid primary key default gen_random_uuid(),
  trip_id uuid not null references public.trips(id) on delete cascade,
  leg text not null,
  code text,
  endpoint_from text,
  endpoint_from_sub text,
  endpoint_to text,
  endpoint_to_sub text,
  note text,
  sort_order int not null default 0
);

alter table public.flights enable row level security;

-- Create the Thanksgiving trip row if it doesn't exist.
-- This is needed for the data migration to have a target.
insert into public.trips (slug, name, home_timezone, destination_timezone, pin_hash, starts_at, starts_terminal, ends_at, ends_terminal)
values (
  'thanksgiving-london-2026',
  'Thanksgiving, London',
  'America/Denver',
  'Europe/London',
  crypt('unused', gen_salt('bf')),
  '2026-11-22 09:15:00+00',
  'LHR T2',
  '2026-11-30 16:10:00+00',
  'LHR T5'
)
on conflict (slug) do nothing;
