-- Bespoke Interval — core schema
-- Private, two-traveler itinerary planner. Every table is queried exclusively
-- by the FastAPI backend using the Supabase service-role key (which bypasses
-- RLS), so RLS is enabled with NO permissive policies: the data is private
-- and there is no case where the anon/public key should read or write it
-- directly.

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
  who text not null default 'Both' check (who in ('Dana','Chris','Both')),
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
  who text not null default 'Both' check (who in ('Dana','Chris','Both')),
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
