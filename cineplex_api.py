"""Cineplex API client — endpoints, seat parsing, and seat-analysis helpers.

Discovered July 2026. Two API surfaces:

1. Theatrical API (showtimes, movies, dates)
   Base: https://apis.cineplex.com/prod/cpx/theatrical/api
   Auth: Ocp-Apim-Subscription-Key header (extracted from Cineplex web JS)

2. Ticketing API (seat availability, seat layout)
   Base: https://apis.cineplex.com/prod/ticketing/api
   Auth: none, but needs a browser-like User-Agent

   /seat-availability → {seat_id: 'Available'|'Occupied'}
   /seat-layout → per-seat types: Standard | Wheelchair | Companion
   (authoritative source for accessible seating — do NOT infer it from
   missing edge columns: front-row curvature causes false positives)

Seat IDs are "{auditorium}_{row}_{seat}". Row numbering is REVERSED
relative to the Cineplex UI: API row 1 = back row (K), API row 12 =
front row (A, nearest screen). The IMAX auditorium has an aisle between
API rows 8 (E) and 6 (F) — API row 7 is absent.
"""

import urllib.request
import urllib.parse
import json
from collections import defaultdict

# ---- constants ----

SUBSCRIPTION_KEY = "dcdac5601d864addbc2675a2e96cb1f8"

THEATRICAL_BASE = "https://apis.cineplex.com/prod/cpx/theatrical/api"
TICKETING_BASE = "https://apis.cineplex.com/prod/ticketing/api"
TICKETING_WEB = "https://www.cineplex.com/ticketing/preview"

CENTRE_COL = 18.0          # ~middle of 1..35 seat columns
FRONT_ROWS = {12, 11, 10}  # A, B, C — too close for good IMAX

# API row → Cineplex letter.  A (nearest screen) = 12 … K (back wall) = 1
ROW_TO_LETTER = {12: "A", 11: "B", 10: "C", 9: "D", 8: "E",
                 6: "F", 5: "G", 4: "H", 3: "I", 2: "J", 1: "K"}

# Display order: front-to-back with aisle between E and F
DISPLAY_ORDER = [
    (12, "A"), (11, "B"), (10, "C"), (9, "D"), (8, "E"),
    None,  # aisle
    (6, "F"), (5, "G"), (4, "H"), (3, "I"), (2, "J"), (1, "K"),
]

DEPTH_ORDER = [12, 11, 10, 9, 8, 6, 5, 4, 3, 2, 1]  # 0 = front A

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def _get_json(base, path, params=None, *, use_key=True):
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if use_key:
        headers["Ocp-Apim-Subscription-Key"] = SUBSCRIPTION_KEY
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


# ---- theatrical API ----

def get_dates(location_id, film_id=None):
    """Return list of ISO date strings like '2026-07-17T00:00:00'."""
    params = {"LocationId": str(location_id)}
    if film_id:
        params["FilmId"] = str(film_id)
    return _get_json(THEATRICAL_BASE, "/v1/dates/bookable", params)


def get_showtimes(location_id, date, film_id=None):
    """Return raw showtimes response for one date."""
    params = {"LocationId": str(location_id), "Date": date}
    if film_id:
        params["FilmId"] = str(film_id)
    return _get_json(THEATRICAL_BASE, "/v1/showtimes", params)


def iter_sessions(showtimes_data, film_id=None, experience_filter=None):
    """Yield (date_str, movie_dict, experience_dict, session_dict)
    from the raw showtimes response (a list of theatre blocks), optionally
    filtering by film or experience type (e.g. 'IMAX')."""
    if isinstance(showtimes_data, dict):
        showtimes_data = [showtimes_data]
    for theatre_data in showtimes_data:
        for date_entry in theatre_data.get("dates", []):
            date = date_entry.get("startDate", "")[:10]
            for movie in date_entry.get("movies", []):
                if film_id and str(movie.get("id")) != str(film_id):
                    continue
                for exp in movie.get("experiences", []):
                    types = exp.get("experienceTypes", [])
                    if experience_filter and not any(
                            experience_filter.lower() in t.lower()
                            for t in types):
                        continue
                    for sess in exp.get("sessions", []):
                        yield date, movie, exp, sess


# ---- ticketing API ----

def get_seat_availability(theatre_id, showtime_id, dbox=False):
    return _get_json(
        TICKETING_BASE,
        f"/v1/theatre/{theatre_id}/showtime/{showtime_id}/seat-availability",
        {"dbox": str(dbox).lower()},
        use_key=False,
    )


def get_seat_layout(theatre_id, showtime_id):
    """Fetch the auditorium seat layout (per-seat types)."""
    return _get_json(
        TICKETING_BASE,
        f"/v1/theatre/{theatre_id}/showtime/{showtime_id}/seat-layout",
        use_key=False,
    )


def parse_seat_layout(layout):
    """Return {(api_row, col): 'Wheelchair'|'Companion'} for every
    non-Standard seat in a seat-layout response.  Layout is auditorium-level,
    so one fetch covers all showtimes in the same auditorium."""
    special = {}
    for area_key in ("standardSeats", "dboxSeats", "balconySeats"):
        area = layout.get(area_key) or {}
        for row in area.get("rows", []):
            for seat in row.get("seats", []):
                stype = seat.get("type")
                if stype and stype != "Standard":
                    _, r, c = map(int, seat["id"].split("_"))
                    special[(r, c)] = stype
    return special


def parse_seats(seat_availabilities):
    """Return {api_row: {seat_col: 'Available'|'Occupied'}}."""
    byrow = defaultdict(dict)
    for seat_id, status in seat_availabilities.items():
        _, row, col = map(int, seat_id.split("_"))
        byrow[row][col] = status
    return dict(byrow)


def booking_url(theatre_id, showtime_id, dbox=False):
    return (f"{TICKETING_WEB}?theatreId={theatre_id}"
            f"&showtimeId={showtime_id}&dbox={str(dbox).lower()}")


# ---- seat analysis ----

def _runs_of_available(seats_in_row):
    """Return list of (start,col, end,col) for each consecutive-Available run."""
    avail = sorted(c for c, st in seats_in_row.items() if st == "Available")
    runs = []
    if not avail:
        return runs
    start = prev = avail[0]
    for s in avail[1:]:
        if s == prev + 1:
            prev = s
        else:
            runs.append((start, prev))
            start = prev = s
    runs.append((start, prev))
    return runs


def triples(byrow, min_run=3, skip_front=True, skip_seats=frozenset()):
    """Yield (api_row, first_seat) for every block of *min_run* consecutive
    Available seats.  If *skip_front*, skips FRONT_ROWS (A,B,C).
    *skip_seats* holds (api_row, col) seats treated as unavailable —
    e.g. Wheelchair spaces, which are not bookable as regular seats."""
    for api, cols in byrow.items():
        if skip_front and api in FRONT_ROWS:
            continue
        cols = {c: st for c, st in cols.items() if (api, c) not in skip_seats}
        for run_start, run_end in _runs_of_available(cols):
            for s in range(run_start, run_end - min_run + 2):
                yield api, s


def depth(api_row):
    """0 = front A … 10 = back K."""
    return DEPTH_ORDER.index(api_row)


def wheelchair_seats(special_seats):
    """Return set of (api_row, col) for Wheelchair-type seats only
    (Companion seats stay bookable trio candidates)."""
    return {rc for rc, t in special_seats.items() if t == "Wheelchair"}


def best_centered_triple(byrow, skip_seats=frozenset()):
    """Return (api_row, first_seat, off_centre, depth) for the best centered
    3-block not in front rows, or None.  Prefers centre column and mid-auditorium."""
    best = None
    for api, s in triples(byrow, skip_seats=skip_seats):
        off = abs(s + 1 - CENTRE_COL)
        score = off + abs(depth(api) - 5) * 2.0
        cand = (score, api, s, off, depth(api))
        if best is None or cand[0] < best[0]:
            best = cand
    if best:
        _, api, s, off, d = best
        return api, s, off, d
    return None


def best_furthest_triple(byrow, skip_seats=frozenset()):
    """Return (api_row, first_seat, off_centre, depth) for the 3-block
    furthest from the screen (highest depth), or None.  Ties broken by
    how close to centre."""
    best = None
    for api, s in triples(byrow, skip_seats=skip_seats):
        off = abs(s + 1 - CENTRE_COL)
        cand = (-depth(api), off, api, s, depth(api))
        if best is None or cand[:2] < best[:2]:
            best = cand
    if best:
        _, _, api, s, d = best
        return api, s, abs(s + 1 - CENTRE_COL), d
    return None
