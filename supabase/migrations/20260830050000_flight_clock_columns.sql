-- The "vacation clock" (trips.starts_at/ends_at) was a separate, manually
-- set pair of columns disconnected from the flights a traveler actually
-- edits — editing a flight leg's display text never moved the clock.
--
-- This adds real timestamps to flights, plus two flags marking which single
-- leg's arrival starts the clock (wheels down at the destination) and which
-- single leg's departure ends it (wheels up leaving the destination). The
-- app now derives the clock from these flagged legs when present, falling
-- back to trips.starts_at/ends_at otherwise.

alter table public.flights
  add column if not exists departs_at timestamptz,
  add column if not exists arrives_at timestamptz,
  add column if not exists is_trip_start boolean not null default false,
  add column if not exists is_trip_end boolean not null default false;

create unique index if not exists flights_one_trip_start_per_trip
  on public.flights (trip_id) where is_trip_start;

create unique index if not exists flights_one_trip_end_per_trip
  on public.flights (trip_id) where is_trip_end;

-- Best-effort backfill: flag the seeded placeholder legs, if they're still
-- present and unflagged, using the trip's existing starts_at/ends_at.
update public.flights
set is_trip_start = true, arrives_at = (select starts_at from public.trips where id = flights.trip_id)
where leg = 'Trip starts · wheels down' and not is_trip_start;

update public.flights
set is_trip_end = true, departs_at = (select ends_at from public.trips where id = flights.trip_id)
where leg = 'Trip ends · wheels up' and not is_trip_end;
