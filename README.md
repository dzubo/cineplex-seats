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

## Files

- `cineplex_api.py` — Cineplex API client (theatrical + ticketing endpoints,
  seat parsing/analysis)
- `gen_seatmaps.py` — generates a self-contained HTML page of SVG seat maps
  per showtime
- `scan.py` — CLI per-day seat-availability report
