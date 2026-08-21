# cineplex-seats

Tools for checking IMAX seat availability at Cineplex theatres. The project
queries Cineplex's ticketing API across dates and showtimes, analyzes seat
layouts, and reports or visualizes availability — highlighting good 3-seat
blocks (centered, mid/back) and wheelchair/companion seats.

Python 3, standard library only — no `pip install` needed.

## Usage

Per-day seat-availability report:

```sh
python3 scan.py 9406 37617 --film-name "The Odyssey" --experience IMAX
```

Generate a self-contained HTML page of SVG seat maps (one per showtime):

```sh
python3 gen_seatmaps.py 9406 37617 --film-name "The Odyssey" --experience IMAX \
    --theatre-name "Cinéma Banque Scotia Montréal" -o /tmp/seats.html
```

Positional arguments are `LOCATION_ID` and `FILM_ID` (defaults: `9406` /
`37617` — Cinéma Banque Scotia Montréal, *The Odyssey*, IMAX).

## Finding your IDs

The two positional arguments are internal Cineplex IDs with no user-facing
source. Use `find.py` to list every film playing at a theatre, with its
`FILM_ID` and available experiences:

```sh
# All films at theatre 9406 today (first bookable date)
python3 find.py 9406

# Filter by title substring; pick a specific day
python3 find.py 9406 --film odyssey --date 2026-08-22
```

Manual fallback: open cineplex.com, pick a theatre + movie, and read the
`LocationId=…` / `FilmId=…` query params from the site's XHR calls to
`apis.cineplex.com` (DevTools → Network).

## Files

- `cineplex_api.py` — Cineplex API client (theatrical + ticketing endpoints,
  seat parsing/analysis)
- `find.py` — ID lookup: lists films (and FILM_IDs) playing at a theatre
- `gen_seatmaps.py` — generates a self-contained HTML page of SVG seat maps
  per showtime
- `scan.py` — CLI per-day seat-availability report
