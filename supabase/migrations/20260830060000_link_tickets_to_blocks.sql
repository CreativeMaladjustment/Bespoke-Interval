-- Tickets, flights, and the calendar (Week/Day view) were entirely
-- separate: the calendar renders only from `blocks`, so a ticket with a
-- real occurs_at (a show time, a timed entry) or a flight leg never showed
-- up on the schedule.
--
-- Adds an optional link from a block to the ticket or flight leg it was
-- generated from. The app keeps at most one such block per ticket/flight
-- in sync whenever the ticket/flight is saved, and deleting either side
-- deletes the other (the FK handles ticket/flight -> block; the app
-- handles block -> ticket/flight, since Postgres has no "cascade upward"
-- direction).

alter table public.blocks
  add column if not exists ticket_id uuid references public.tickets(id) on delete cascade,
  add column if not exists flight_id uuid references public.flights(id) on delete cascade;

create unique index if not exists blocks_ticket_id_key
  on public.blocks (ticket_id) where ticket_id is not null;

create unique index if not exists blocks_flight_id_key
  on public.blocks (flight_id) where flight_id is not null;
