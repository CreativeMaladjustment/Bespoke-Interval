-- Seed data for the London, October trip — ported 1:1 from the Claude Design
-- mockup ("London Trip.dc.html"). All Day 1 activity (drive to the airport,
-- check-in, the outbound flight) is stored in true America/Denver local time;
-- everything from wheels-down at Heathrow onward is true Europe/London local
-- time, using real timestamptz values rather than the mockup's fixed
-- "subtract 7 hours" placeholder so the timezone toggle in the app is
-- actually correct (both zones stay on their October 2026 DST offset for the
-- whole trip, so the effective gap is a constant 7 hours either way).
--
-- The shared sign-in code seeded here is 4610 — change it after your first
-- deploy with:
--   update public.trips set pin_hash = crypt('<new code>', gen_salt('bf'))
--   where slug = 'london-october';

insert into public.trips (slug, name, home_timezone, destination_timezone, pin_hash, starts_at, starts_terminal, ends_at, ends_terminal)
values (
  'london-october',
  'London, October',
  'America/Denver',
  'Europe/London',
  crypt('4610', gen_salt('bf')),
  '2026-10-04 11:45:00+01',
  'LHR T2',
  '2026-10-12 15:20:00+01',
  'LHR T5'
)
on conflict (slug) do nothing;

insert into public.travelers (trip_id, name, initial, role, sort_order)
select t.id, v.name, v.initial, v.role, v.sort_order
from public.trips t,
  (values
    ('Dana', 'D', 'Trip owner', 0),
    ('Chris', 'C', 'Traveller', 1)
  ) as v(name, initial, role, sort_order)
where t.slug = 'london-october';

insert into public.trip_days (trip_id, day_index, calendar_date, reference_timezone, kicker, tag)
select t.id, v.day_index, v.calendar_date, v.reference_timezone, v.kicker, v.tag
from public.trips t,
  (values
    (1, date '2026-10-03', 'America/Denver', 'Denver → in the air', 'Depart DEN'),
    (2, date '2026-10-04', 'Europe/London', 'Vacation clock starts 11:45', 'Land LHR'),
    (3, date '2026-10-05', 'Europe/London', 'First full day', 'Museums'),
    (4, date '2026-10-06', 'Europe/London', 'Reading day', 'Library'),
    (5, date '2026-10-07', 'Europe/London', 'Open day', 'Free'),
    (6, date '2026-10-08', 'Europe/London', 'Day trip', 'Greenwich'),
    (7, date '2026-10-09', 'Europe/London', 'Matinee day', 'Matinee'),
    (8, date '2026-10-10', 'Europe/London', 'Slow day', 'Open'),
    (9, date '2026-10-11', 'Europe/London', 'Last full day', 'Last day'),
    (10, date '2026-10-12', 'Europe/London', 'Vacation clock stops 15:20', 'Fly home')
  ) as v(day_index, calendar_date, reference_timezone, kicker, tag)
where t.slug = 'london-october';

with t as (select id as trip_id from public.trips where slug = 'london-october'),
     td as (select day_index, id as trip_day_id from public.trip_days join t on trip_days.trip_id = t.trip_id)
insert into public.blocks (trip_id, trip_day_id, type, title, subtitle, starts_at, ends_at, who)
select t.trip_id, td.trip_day_id, v.type, v.title, v.subtitle, v.starts_at, v.ends_at, v.who
from t, td,
  (values
    (1, 'transit', 'Drive to DEN', 'A-Line from Union Station · 45 min', '2026-10-03 12:30:00-06'::timestamptz, '2026-10-03 14:00:00-06'::timestamptz, 'Both'),
    (1, 'travel', 'DEN Terminal · check bags', 'UA 928 · gate B44', '2026-10-03 14:00:00-06'::timestamptz, '2026-10-03 16:30:00-06'::timestamptz, 'Both'),
    (1, 'travel', 'UA 928 DEN → LHR', 'Overnight · 8h 45m · lands 11:45 tomorrow', '2026-10-03 16:30:00-06'::timestamptz, '2026-10-04 11:45:00+01'::timestamptz, 'Both'),

    (2, 'travel', 'Land LHR T2 · border', 'Wheels down 11:45 — trip officially starts', '2026-10-04 11:45:00+01'::timestamptz, '2026-10-04 13:00:00+01'::timestamptz, 'Both'),
    (2, 'transit', 'Heathrow Express + tube', 'Paddington → Russell Square', '2026-10-04 13:00:00+01'::timestamptz, '2026-10-04 14:15:00+01'::timestamptz, 'Both'),
    (2, 'rest', 'Hotel check-in, drop bags', 'Bloomsbury · room ready 14:00', '2026-10-04 14:15:00+01'::timestamptz, '2026-10-04 15:00:00+01'::timestamptz, 'Both'),
    (2, 'walk', 'Walk: Bloomsbury squares', 'Slow loop to shake off the flight', '2026-10-04 15:00:00+01'::timestamptz, '2026-10-04 16:45:00+01'::timestamptz, 'Both'),
    (2, 'meal', 'Early dinner', 'Booked 17:00 · 8 min walk from hotel', '2026-10-04 17:00:00+01'::timestamptz, '2026-10-04 18:15:00+01'::timestamptz, 'Both'),
    (2, 'transit', 'Travel to the Aldwych', 'Auto-blocked for the 19:30 curtain', '2026-10-04 18:30:00+01'::timestamptz, '2026-10-04 19:15:00+01'::timestamptz, 'Both'),
    (2, 'theatre', 'The Winter Ledger', 'Aldwych Theatre · stalls H12–H13', '2026-10-04 19:30:00+01'::timestamptz, '2026-10-04 22:15:00+01'::timestamptz, 'Both'),

    (3, 'meal', 'Breakfast at the hotel', null, '2026-10-05 09:00:00+01'::timestamptz, '2026-10-05 09:45:00+01'::timestamptz, 'Both'),
    (3, 'museum', 'British Museum', 'Timed entry 10:00 · Rosetta room first', '2026-10-05 10:00:00+01'::timestamptz, '2026-10-05 12:30:00+01'::timestamptz, 'Both'),
    (3, 'meal', 'Lunch, Lamb''s Conduit St', 'No booking — walk-in', '2026-10-05 12:45:00+01'::timestamptz, '2026-10-05 13:45:00+01'::timestamptz, 'Both'),
    (3, 'tourist', 'London Eye', 'Timed slot 16:15 · sunset rotation', '2026-10-05 16:00:00+01'::timestamptz, '2026-10-05 17:30:00+01'::timestamptz, 'Both'),
    (3, 'meal', 'Dinner in Covent Garden', 'Booked 19:00 for two', '2026-10-05 19:00:00+01'::timestamptz, '2026-10-05 20:30:00+01'::timestamptz, 'Both'),

    (4, 'meal', 'Coffee & pastry', null, '2026-10-06 09:30:00+01'::timestamptz, '2026-10-06 10:15:00+01'::timestamptz, 'Both'),
    (4, 'library', 'British Library reading rooms', 'Reader pass collected on arrival', '2026-10-06 10:30:00+01'::timestamptz, '2026-10-06 13:00:00+01'::timestamptz, 'Dana'),
    (4, 'walk', 'Walk: Regent''s Canal', 'King''s Cross → Camden', '2026-10-06 10:30:00+01'::timestamptz, '2026-10-06 12:30:00+01'::timestamptz, 'Chris'),
    (4, 'meal', 'Lunch, Granary Square', null, '2026-10-06 13:15:00+01'::timestamptz, '2026-10-06 14:15:00+01'::timestamptz, 'Both'),
    (4, 'transit', 'Travel to the Barbican', 'Auto-blocked for the 19:45 curtain', '2026-10-06 18:45:00+01'::timestamptz, '2026-10-06 19:15:00+01'::timestamptz, 'Both'),
    (4, 'theatre', 'Measure for Measure', 'Barbican · circle D4–D5', '2026-10-06 19:45:00+01'::timestamptz, '2026-10-06 22:00:00+01'::timestamptz, 'Both'),

    (5, 'meal', 'Breakfast', null, '2026-10-07 09:00:00+01'::timestamptz, '2026-10-07 09:45:00+01'::timestamptz, 'Both'),
    (5, 'museum', 'Sir John Soane''s Museum', 'Free entry · queue before 14:00', '2026-10-07 14:00:00+01'::timestamptz, '2026-10-07 16:00:00+01'::timestamptz, 'Both'),
    (5, 'meal', 'Dinner, Spitalfields', null, '2026-10-07 19:30:00+01'::timestamptz, '2026-10-07 21:00:00+01'::timestamptz, 'Both'),

    (6, 'transit', 'Thames Clipper to Greenwich', 'Embankment pier', '2026-10-08 09:30:00+01'::timestamptz, '2026-10-08 10:30:00+01'::timestamptz, 'Both'),
    (6, 'tourist', 'Royal Observatory', 'Timed 11:00', '2026-10-08 10:30:00+01'::timestamptz, '2026-10-08 13:00:00+01'::timestamptz, 'Both'),
    (6, 'meal', 'Lunch at the market', null, '2026-10-08 13:00:00+01'::timestamptz, '2026-10-08 14:00:00+01'::timestamptz, 'Both'),
    (6, 'walk', 'Walk: Greenwich Park', null, '2026-10-08 14:00:00+01'::timestamptz, '2026-10-08 16:00:00+01'::timestamptz, 'Both'),

    (7, 'museum', 'National Gallery', 'Room 32 onward', '2026-10-09 10:00:00+01'::timestamptz, '2026-10-09 12:00:00+01'::timestamptz, 'Both'),
    (7, 'meal', 'Lunch off Trafalgar Sq', null, '2026-10-09 12:15:00+01'::timestamptz, '2026-10-09 13:15:00+01'::timestamptz, 'Both'),
    (7, 'transit', 'Walk to the theatre', 'Auto-blocked for the 14:30 matinee', '2026-10-09 13:30:00+01'::timestamptz, '2026-10-09 14:00:00+01'::timestamptz, 'Both'),
    (7, 'theatre', 'A Number (matinee)', 'Duke of York''s · row F', '2026-10-09 14:30:00+01'::timestamptz, '2026-10-09 17:00:00+01'::timestamptz, 'Both'),
    (7, 'meal', 'Dinner, Soho', null, '2026-10-09 19:00:00+01'::timestamptz, '2026-10-09 20:30:00+01'::timestamptz, 'Both'),

    (8, 'meal', 'Breakfast', null, '2026-10-10 09:30:00+01'::timestamptz, '2026-10-10 10:30:00+01'::timestamptz, 'Both'),
    (8, 'walk', 'Walk: South Bank to Tate', null, '2026-10-10 11:00:00+01'::timestamptz, '2026-10-10 13:30:00+01'::timestamptz, 'Both'),
    (8, 'meal', 'Dinner near the hotel', null, '2026-10-10 19:00:00+01'::timestamptz, '2026-10-10 20:30:00+01'::timestamptz, 'Both'),

    (9, 'museum', 'V&A', 'Cast courts + jewellery', '2026-10-11 10:00:00+01'::timestamptz, '2026-10-11 12:30:00+01'::timestamptz, 'Both'),
    (9, 'meal', 'Lunch, Brompton Rd', null, '2026-10-11 13:00:00+01'::timestamptz, '2026-10-11 14:00:00+01'::timestamptz, 'Both'),
    (9, 'tourist', 'Tower of London', 'Timed 15:00', '2026-10-11 15:00:00+01'::timestamptz, '2026-10-11 17:00:00+01'::timestamptz, 'Both'),
    (9, 'meal', 'Farewell dinner', 'Booked 19:30', '2026-10-11 19:30:00+01'::timestamptz, '2026-10-11 21:30:00+01'::timestamptz, 'Both'),

    (10, 'meal', 'Breakfast, pack', null, '2026-10-12 09:00:00+01'::timestamptz, '2026-10-12 10:00:00+01'::timestamptz, 'Both'),
    (10, 'rest', 'Check out, bags with concierge', null, '2026-10-12 10:00:00+01'::timestamptz, '2026-10-12 11:00:00+01'::timestamptz, 'Both'),
    (10, 'transit', 'Tube + Heathrow Express', 'Auto-blocked · 3h before wheels-up', '2026-10-12 11:30:00+01'::timestamptz, '2026-10-12 12:45:00+01'::timestamptz, 'Both'),
    (10, 'travel', 'BA 219 LHR → DEN', 'Wheels up 15:20 — trip ends', '2026-10-12 12:45:00+01'::timestamptz, '2026-10-12 18:05:00-06'::timestamptz, 'Both')
  ) as v(day_index, type, title, subtitle, starts_at, ends_at, who)
where td.day_index = v.day_index;

insert into public.tickets (trip_id, category, kind, title, venue, occurs_at, who, facts, sort_order)
select t.id, v.category, v.kind, v.title, v.venue, v.occurs_at, v.who, v.facts::jsonb, v.sort_order
from public.trips t,
  (values
    ('theatre', 'Theatre', 'The Winter Ledger', 'Aldwych Theatre, WC2B 4DF', '2026-10-04 19:30:00+01'::timestamptz, 'Both',
      '[{"k":"Doors / curtain","v":"19:00 / 19:30"},{"k":"Seats","v":"Stalls H12–H13"},{"k":"Ref","v":"ALD-4471"}]', 1),
    ('theatre', 'Theatre', 'Measure for Measure', 'Barbican Centre, EC2Y 8DS', '2026-10-06 19:45:00+01'::timestamptz, 'Both',
      '[{"k":"Doors / curtain","v":"19:15 / 19:45"},{"k":"Seats","v":"Circle D4–D5"},{"k":"Ref","v":"BBC-2290"}]', 2),
    ('theatre', 'Matinee', 'A Number', 'Duke of York''s, St Martin''s Ln', '2026-10-09 14:30:00+01'::timestamptz, 'Both',
      '[{"k":"Doors / curtain","v":"14:00 / 14:30"},{"k":"Seats","v":"Row F 7–8"},{"k":"Ref","v":"DOY-1183"}]', 3),
    ('tourist', 'Attraction', 'London Eye', 'Riverside Building, SE1 7PB', '2026-10-05 16:15:00+01'::timestamptz, 'Both',
      '[{"k":"Slot","v":"16:15, arrive 16:00"},{"k":"Type","v":"Standard, 2 adults"},{"k":"Ref","v":"EYE-88213"}]', 4),
    ('museum', 'Timed entry', 'British Museum', 'Great Russell St, WC1B 3DG', '2026-10-05 10:00:00+01'::timestamptz, 'Both',
      '[{"k":"Entry","v":"10:00"},{"k":"Cost","v":"Free, booked"},{"k":"Ref","v":"BM-70412"}]', 5)
  ) as v(category, kind, title, venue, occurs_at, who, facts, sort_order)
where t.slug = 'london-october';

insert into public.flights (trip_id, leg, code, endpoint_from, endpoint_from_sub, endpoint_to, endpoint_to_sub, note, sort_order)
select t.id, v.leg, v.code, v.endpoint_from, v.endpoint_from_sub, v.endpoint_to, v.endpoint_to_sub, v.note, v.sort_order
from public.trips t,
  (values
    ('Outbound · leaves home', 'UA 928', 'DEN', '3 Oct 16:30 MDT', 'LHR', '4 Oct 11:45 BST',
      'Bags dropped by 14:30 MDT. Denver time only appears on this leg.', 1),
    ('Trip starts · wheels down', 'LHR T2', '11:45', 'Border + bags ≈ 75 min', 'BST', 'Express 13:00',
      'Everything after this is scheduled in London time.', 2),
    ('Trip ends · wheels up', 'BA 219', 'LHR', '12 Oct 15:20 BST', 'DEN', '12 Oct 18:05 MDT',
      'Airport travel auto-blocked from 11:30, three hours before departure.', 3),
    ('Home', 'Ground', 'DEN', '18:05 MDT', 'Home', '19:30 MDT',
      'A-Line to Union Station.', 4)
  ) as v(leg, code, endpoint_from, endpoint_from_sub, endpoint_to, endpoint_to_sub, note, sort_order)
where t.slug = 'london-october';
