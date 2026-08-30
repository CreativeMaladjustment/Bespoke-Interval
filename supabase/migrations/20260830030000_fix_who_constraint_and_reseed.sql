-- Fix: `blocks.who` and `tickets.who` got their check constraint from the very
-- first schema migration (20260830000000), which only allows
-- ('Dana','Chris','Both'). The later schema migration
-- (20260830010000_bootstrap_schema_and_seed.sql) tried to redefine those
-- tables with a ('jd','emy','Both') constraint, but its `create table if not
-- exists` silently no-ops once the tables already exist, so the old
-- constraint stuck around. Every jd/emy row insert in
-- 20260830020000_seed_thanksgiving_data.sql then violated that constraint,
-- which rolled back that whole migration's transaction — including the
-- travelers insert that ran earlier in the same file. Net effect: only the
-- original Dana/Chris data was ever visible.

-- This app now serves a single trip (Thanksgiving, London, for jd and emy);
-- retire the old london-october trip and its rows.
delete from public.trips where slug = 'london-october';

alter table public.blocks drop constraint if exists blocks_who_check;
alter table public.blocks add constraint blocks_who_check check (who in ('jd', 'emy', 'Both'));

alter table public.tickets drop constraint if exists tickets_who_check;
alter table public.tickets add constraint tickets_who_check check (who in ('jd', 'emy', 'Both'));

-- Re-run the Thanksgiving seed now that the constraint allows jd/emy rows.
delete from public.flights where trip_id = (select id from public.trips where slug = 'thanksgiving-london-2026');
delete from public.tickets where trip_id = (select id from public.trips where slug = 'thanksgiving-london-2026');
delete from public.blocks where trip_id = (select id from public.trips where slug = 'thanksgiving-london-2026');
delete from public.trip_days where trip_id = (select id from public.trips where slug = 'thanksgiving-london-2026');
delete from public.travelers where trip_id = (select id from public.trips where slug = 'thanksgiving-london-2026');

insert into public.travelers (trip_id, name, initial, role, sort_order)
select t.id, v.name, v.initial, v.role, v.sort_order
from public.trips t,
  (values
    ('jd', 'j', 'Trip owner', 0),
    ('emy', 'e', 'Traveller', 1)
  ) as v(name, initial, role, sort_order)
where t.slug = 'thanksgiving-london-2026';

insert into public.trip_days (trip_id, day_index, calendar_date, reference_timezone, kicker, tag)
select t.id, v.day_index, v.calendar_date, v.reference_timezone, v.kicker, v.tag
from public.trips t,
  (values
    (1, date '2026-11-21', 'America/Denver', 'Denver → in the air', 'Depart DEN'),
    (2, date '2026-11-22', 'Europe/London', 'Vacation clock starts 09:15', 'Land LHR'),
    (3, date '2026-11-23', 'Europe/London', 'First full day', 'Markets'),
    (4, date '2026-11-24', 'Europe/London', 'Museum day', 'Museums'),
    (5, date '2026-11-25', 'Europe/London', 'Thanksgiving Eve', 'Prep'),
    (6, date '2026-11-26', 'Europe/London', 'Thanksgiving Day', 'Feast'),
    (7, date '2026-11-27', 'Europe/London', 'Theatre night', 'Theatre'),
    (8, date '2026-11-28', 'Europe/London', 'Gallery day', 'Galleries'),
    (9, date '2026-11-29', 'Europe/London', 'Last full day', 'Last day'),
    (10, date '2026-11-30', 'Europe/London', 'Vacation clock stops 16:10', 'Fly home')
  ) as v(day_index, calendar_date, reference_timezone, kicker, tag)
where t.slug = 'thanksgiving-london-2026';

with t as (select id as trip_id from public.trips where slug = 'thanksgiving-london-2026'),
     td as (select day_index, id as trip_day_id from public.trip_days join t on trip_days.trip_id = t.trip_id)
insert into public.blocks (trip_id, trip_day_id, type, title, subtitle, starts_at, ends_at, who)
select t.trip_id, td.trip_day_id, v.type, v.title, v.subtitle, v.starts_at, v.ends_at, v.who
from t, td,
  (values
    (1, 'transit', 'Drive to DEN', 'Uber to airport · 30 min', '2026-11-21 07:30:00-07'::timestamptz, '2026-11-21 08:00:00-07'::timestamptz, 'Both'),
    (1, 'travel', 'DEN Terminal · check bags', 'BA 119 · gate C22', '2026-11-21 08:00:00-07'::timestamptz, '2026-11-21 08:45:00-07'::timestamptz, 'Both'),
    (1, 'travel', 'BA 119 DEN → LHR', 'Overnight · 9h 30m · lands 09:15 tomorrow', '2026-11-21 08:45:00-07'::timestamptz, '2026-11-22 09:15:00+00'::timestamptz, 'Both'),

    (2, 'travel', 'Land LHR T2 · border', 'Wheels down 09:15 — trip officially starts', '2026-11-22 09:15:00+00'::timestamptz, '2026-11-22 10:30:00+00'::timestamptz, 'Both'),
    (2, 'transit', 'Heathrow Express + tube', 'Paddington → Bloomsbury', '2026-11-22 10:30:00+00'::timestamptz, '2026-11-22 11:45:00+00'::timestamptz, 'Both'),
    (2, 'rest', 'Hotel check-in, drop bags', 'Bloomsbury · room ready 11:30', '2026-11-22 11:45:00+00'::timestamptz, '2026-11-22 13:00:00+00'::timestamptz, 'Both'),
    (2, 'walk', 'Walk: Bloomsbury squares', 'Slow loop to shake off the flight', '2026-11-22 13:00:00+00'::timestamptz, '2026-11-22 15:00:00+00'::timestamptz, 'Both'),
    (2, 'meal', 'Early dinner', 'Cosy pub near hotel', '2026-11-22 17:00:00+00'::timestamptz, '2026-11-22 18:15:00+00'::timestamptz, 'Both'),

    (3, 'meal', 'Breakfast at the hotel', null, '2026-11-23 08:00:00+00'::timestamptz, '2026-11-23 09:00:00+00'::timestamptz, 'Both'),
    (3, 'walk', 'Borough Market & South Bank', 'Walk and browse the markets', '2026-11-23 09:30:00+00'::timestamptz, '2026-11-23 12:30:00+00'::timestamptz, 'Both'),
    (3, 'meal', 'Lunch at the market', 'Borough Market vendors', '2026-11-23 12:45:00+00'::timestamptz, '2026-11-23 13:45:00+00'::timestamptz, 'Both'),
    (3, 'tourist', 'Christmas market at South Bank', 'Early holiday market exploration', '2026-11-23 14:00:00+00'::timestamptz, '2026-11-23 16:30:00+00'::timestamptz, 'Both'),
    (3, 'meal', 'Dinner in Borough', 'Restaurant near the market', '2026-11-23 18:00:00+00'::timestamptz, '2026-11-23 19:30:00+00'::timestamptz, 'Both'),

    (4, 'meal', 'Coffee & pastry', null, '2026-11-24 09:00:00+00'::timestamptz, '2026-11-24 09:45:00+00'::timestamptz, 'Both'),
    (4, 'museum', 'British Museum', 'Timed entry 10:30 · Egyptian wing', '2026-11-24 10:30:00+00'::timestamptz, '2026-11-24 13:00:00+00'::timestamptz, 'jd'),
    (4, 'walk', 'Walk: Regent''s Canal', 'King''s Cross → Camden Market', '2026-11-24 10:30:00+00'::timestamptz, '2026-11-24 12:30:00+00'::timestamptz, 'emy'),
    (4, 'meal', 'Lunch, Covent Garden', 'No booking — walk-in', '2026-11-24 13:15:00+00'::timestamptz, '2026-11-24 14:15:00+00'::timestamptz, 'Both'),
    (4, 'transit', 'Travel to the National Gallery', 'Auto-blocked for afternoon visit', '2026-11-24 14:30:00+00'::timestamptz, '2026-11-24 15:00:00+00'::timestamptz, 'Both'),
    (4, 'museum', 'National Gallery', 'Room 32 onward · impressionist wing', '2026-11-24 15:00:00+00'::timestamptz, '2026-11-24 17:00:00+00'::timestamptz, 'Both'),
    (4, 'meal', 'Dinner near Leicester Square', 'Booked 19:00', '2026-11-24 19:00:00+00'::timestamptz, '2026-11-24 20:30:00+00'::timestamptz, 'Both'),

    (5, 'meal', 'Breakfast', null, '2026-11-25 08:30:00+00'::timestamptz, '2026-11-25 09:30:00+00'::timestamptz, 'Both'),
    (5, 'walk', 'Shopping for Thanksgiving', 'Marks & Spencer, Fortnum & Mason, specialty shops', '2026-11-25 10:00:00+00'::timestamptz, '2026-11-25 13:00:00+00'::timestamptz, 'jd'),
    (5, 'walk', 'Christmas market browsing', 'South Bank and Southbank Centre', '2026-11-25 10:00:00+00'::timestamptz, '2026-11-25 12:30:00+00'::timestamptz, 'emy'),
    (5, 'meal', 'Lunch', null, '2026-11-25 13:15:00+00'::timestamptz, '2026-11-25 14:15:00+00'::timestamptz, 'Both'),
    (5, 'rest', 'Hotel rest & prep', 'Thanksgiving meal prep time', '2026-11-25 15:00:00+00'::timestamptz, '2026-11-25 18:00:00+00'::timestamptz, 'jd'),
    (5, 'walk', 'Afternoon wander', 'Explore side streets', '2026-11-25 14:30:00+00'::timestamptz, '2026-11-25 17:00:00+00'::timestamptz, 'emy'),
    (5, 'meal', 'Light dinner', 'Save room for tomorrow', '2026-11-25 18:30:00+00'::timestamptz, '2026-11-25 19:30:00+00'::timestamptz, 'Both'),

    (6, 'meal', 'Thanksgiving morning breakfast', 'Late breakfast at 09:00', '2026-11-26 09:00:00+00'::timestamptz, '2026-11-26 10:00:00+00'::timestamptz, 'Both'),
    (6, 'rest', 'Relax & afternoon prep', 'Thanksgiving feast preparation', '2026-11-26 11:00:00+00'::timestamptz, '2026-11-26 17:00:00+00'::timestamptz, 'jd'),
    (6, 'walk', 'Afternoon walk in parks', 'Green spaces & relaxation', '2026-11-26 11:00:00+00'::timestamptz, '2026-11-26 16:00:00+00'::timestamptz, 'emy'),
    (6, 'meal', 'Thanksgiving feast', 'Dinner at 18:00 · special celebration', '2026-11-26 18:00:00+00'::timestamptz, '2026-11-26 20:00:00+00'::timestamptz, 'Both'),
    (6, 'rest', 'Drinks & dessert', 'Evening celebration', '2026-11-26 20:00:00+00'::timestamptz, '2026-11-26 21:30:00+00'::timestamptz, 'Both'),

    (7, 'meal', 'Breakfast', null, '2026-11-27 08:00:00+00'::timestamptz, '2026-11-27 09:00:00+00'::timestamptz, 'Both'),
    (7, 'transit', 'Travel to the Barbican', 'Auto-blocked for the 19:45 curtain', '2026-11-27 18:45:00+00'::timestamptz, '2026-11-27 19:15:00+00'::timestamptz, 'Both'),
    (7, 'meal', 'Pre-theatre dinner', 'Restaurant near theatre', '2026-11-27 17:00:00+00'::timestamptz, '2026-11-27 18:15:00+00'::timestamptz, 'Both'),
    (7, 'theatre', 'Shakespeare at Barbican', 'Evening performance · circle seats', '2026-11-27 19:45:00+00'::timestamptz, '2026-11-27 22:15:00+00'::timestamptz, 'Both'),

    (8, 'meal', 'Breakfast', null, '2026-11-28 09:00:00+00'::timestamptz, '2026-11-28 09:45:00+00'::timestamptz, 'Both'),
    (8, 'museum', 'Tate Modern', 'Modern art collections', '2026-11-28 10:30:00+00'::timestamptz, '2026-11-28 13:00:00+00'::timestamptz, 'Both'),
    (8, 'meal', 'Lunch, South Bank', null, '2026-11-28 13:15:00+00'::timestamptz, '2026-11-28 14:15:00+00'::timestamptz, 'Both'),
    (8, 'walk', 'Walk: Millennium Bridge & St Paul''s', null, '2026-11-28 14:30:00+00'::timestamptz, '2026-11-28 16:30:00+00'::timestamptz, 'Both'),
    (8, 'meal', 'Dinner in Shoreditch', 'Trendy neighbourhood', '2026-11-28 19:00:00+00'::timestamptz, '2026-11-28 20:30:00+00'::timestamptz, 'Both'),

    (9, 'meal', 'Breakfast', null, '2026-11-29 08:00:00+00'::timestamptz, '2026-11-29 09:00:00+00'::timestamptz, 'Both'),
    (9, 'museum', 'V&A Museum', 'Design & decorative arts', '2026-11-29 10:00:00+00'::timestamptz, '2026-11-29 12:30:00+00'::timestamptz, 'Both'),
    (9, 'meal', 'Lunch, Brompton Road', null, '2026-11-29 13:00:00+00'::timestamptz, '2026-11-29 14:00:00+00'::timestamptz, 'Both'),
    (9, 'walk', 'Walk: Kensington Gardens', 'Last day stroll', '2026-11-29 14:30:00+00'::timestamptz, '2026-11-29 16:30:00+00'::timestamptz, 'Both'),
    (9, 'meal', 'Farewell dinner', 'Booked 19:30 · special venue', '2026-11-29 19:30:00+00'::timestamptz, '2026-11-29 21:30:00+00'::timestamptz, 'Both'),

    (10, 'meal', 'Breakfast, pack', null, '2026-11-30 08:00:00+00'::timestamptz, '2026-11-30 09:00:00+00'::timestamptz, 'Both'),
    (10, 'rest', 'Check out, bags with concierge', null, '2026-11-30 09:00:00+00'::timestamptz, '2026-11-30 10:00:00+00'::timestamptz, 'Both'),
    (10, 'transit', 'Tube + Heathrow Express', 'Auto-blocked · 3h before wheels-up', '2026-11-30 13:00:00+00'::timestamptz, '2026-11-30 14:15:00+00'::timestamptz, 'Both'),
    (10, 'travel', 'BA 120 LHR → DEN', 'Wheels up 16:10 — trip ends', '2026-11-30 14:15:00+00'::timestamptz, '2026-11-30 16:10:00-07'::timestamptz, 'Both')
  ) as v(day_index, type, title, subtitle, starts_at, ends_at, who)
where td.day_index = v.day_index;

insert into public.tickets (trip_id, category, kind, title, venue, occurs_at, who, facts, sort_order)
select t.id, v.category, v.kind, v.title, v.venue, v.occurs_at, v.who, v.facts::jsonb, v.sort_order
from public.trips t,
  (values
    ('theatre', 'Theatre', 'Shakespeare at Barbican', 'Barbican Centre, EC2Y 8DS', '2026-11-27 19:45:00+00'::timestamptz, 'Both',
      '[{"k":"Doors / curtain","v":"19:15 / 19:45"},{"k":"Seats","v":"Circle D4–D5"},{"k":"Ref","v":"BBC-2342"}]', 1),
    ('museum', 'Timed entry', 'British Museum', 'Great Russell St, WC1B 3DG', '2026-11-24 10:30:00+00'::timestamptz, 'jd',
      '[{"k":"Entry","v":"10:30"},{"k":"Cost","v":"Free, suggested donation"},{"k":"Ref","v":"BM-71289"}]', 2),
    ('museum', 'Exhibition', 'Tate Modern', 'Bankside, SE1 9TG', '2026-11-28 10:30:00+00'::timestamptz, 'Both',
      '[{"k":"Entry","v":"Free"},{"k":"Must see","v":"Current special exhibition"},{"k":"Ref","v":"TM-55012"}]', 3),
    ('museum', 'Timed entry', 'National Gallery', 'Trafalgar Square, WC2N 5DN', '2026-11-24 15:00:00+00'::timestamptz, 'Both',
      '[{"k":"Entry","v":"Free, suggested donation"},{"k":"Duration","v":"2 hours planned"},{"k":"Ref","v":"NG-44723"}]', 4),
    ('tourist', 'Market', 'Borough Market', 'SE1 9AH', '2026-11-23 12:45:00+00'::timestamptz, 'Both',
      '[{"k":"Type","v":"Historic food market"},{"k":"Hours","v":"11am–5pm Wed–Thu, later Fri–Sat"},{"k":"Ref","v":"BM-FOOD-23"}]', 5)
  ) as v(category, kind, title, venue, occurs_at, who, facts, sort_order)
where t.slug = 'thanksgiving-london-2026';

insert into public.flights (trip_id, leg, code, endpoint_from, endpoint_from_sub, endpoint_to, endpoint_to_sub, note, sort_order)
select t.id, v.leg, v.code, v.endpoint_from, v.endpoint_from_sub, v.endpoint_to, v.endpoint_to_sub, v.note, v.sort_order
from public.trips t,
  (values
    ('Outbound · leaves home', 'BA 119', 'DEN', '21 Nov 08:45 MST', 'LHR', '22 Nov 09:15 GMT',
      'Bags dropped by 08:00 MST. Denver time only appears on this leg.', 1),
    ('Trip starts · wheels down', 'LHR T2', '09:15', 'Border + bags ≈ 75 min', 'GMT', 'Express 11:45',
      'Everything after this is scheduled in London time.', 2),
    ('Trip ends · wheels up', 'BA 120', 'LHR', '30 Nov 16:10 GMT', 'DEN', '30 Nov 16:10 MST',
      'Airport travel auto-blocked from 13:00, three hours before departure.', 3),
    ('Home', 'Ground', 'DEN', '16:10 MST', 'Home', '17:30 MST',
      'Uber/ride from airport.', 4)
  ) as v(leg, code, endpoint_from, endpoint_from_sub, endpoint_to, endpoint_to_sub, note, sort_order)
where t.slug = 'thanksgiving-london-2026';
