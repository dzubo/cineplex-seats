# cineplex-seats

Check IMAX seat availability at Cineplex theatres (Canada only). Two tools:

- `scan.py` — per-day report in your terminal: free seats, best 3-seat blocks
- `gen_seatmaps.py` — self-contained HTML page of seat maps you can scroll

Python 3, standard library only — no `pip install` needed.

## Quick start

With no arguments both tools check *The Odyssey* in IMAX at Cinéma Banque
Scotia Montréal:

```sh
python3 scan.py            # terminal report
python3 gen_seatmaps.py    # writes /tmp/cineplex-seatmaps.html, open it in a browser
```

`scan.py` prints something like:

```
date       shows   seats centered?  best centered triples  │  furthest-back triple
----------------------------------------------------------------------------------
2026-09-02     4     281  0/4      D4–D6 (13 off)        │  D4–D6 (13 off)
2026-09-03     4     274  0/4      D5–D7 (12 off)        │  D4–D6 (13 off)
...

Overall: 27 days, 99 showtimes.
Days with >=1 centered mid/back 3-block: 0/27.
```

A "centered" triple is 3 seats together within ~4 seats of centre, not in
front rows A–C.

## Other theatres and movies

Find a theatre with `theatres.py`, then its films with `find.py`:

```sh
python3 theatres.py --search montreal    # all theatres matching text
python3 theatres.py                      # every Cineplex theatre in Canada

python3 find.py 9406                     # films at theatre 9406 today
python3 find.py 9406 --film odyssey --date 2026-08-22   # filter by title / day
```

Then pass the two IDs plus optional flags:

```sh
python3 scan.py 9406 37617 --film-name "The Odyssey" --experience IMAX

python3 gen_seatmaps.py 9406 37617 \
    --film-name "The Odyssey" --experience IMAX \
    --theatre-name "Cinéma Banque Scotia Montréal" -o /tmp/seats.html
```

If `find.py` doesn't cover your case: open cineplex.com, pick a theatre +
movie, and read the `LocationId=…` / `FilmId=…` params from the site's XHR
calls to `apis.cineplex.com` (DevTools → Network).

## Files

- `cineplex_api.py` — Cineplex API client (theatrical + ticketing endpoints,
  seat parsing/analysis)
- `find.py` — ID lookup: lists films (and FILM_IDs) playing at a theatre
- `gen_seatmaps.py` — generates a self-contained HTML page of SVG seat maps
  per showtime
- `scan.py` — CLI per-day seat-availability report
- `theatres.py` — lists all Cineplex theatres with their LOCATION_IDs
