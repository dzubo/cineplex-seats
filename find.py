#!/usr/bin/env python3
"""List the films playing at a Cineplex theatre, with their FILM_IDs.

Usage:
  python3 find.py LOCATION_ID [--film SUBSTR] [--date YYYY-MM-DD]

Resolves FILM_IDs so they can be passed to scan.py / gen_seatmaps.py
without digging IDs out of the Cineplex website's network requests.
Default date is the first bookable date at that theatre.
"""
import sys
import re

from urllib.error import HTTPError, URLError

from cineplex_api import get_dates, get_showtimes, iter_sessions


def parse_args(argv):
    if len(argv) < 2:
        sys.exit("usage: python3 find.py LOCATION_ID "
                 "[--film SUBSTR] [--date YYYY-MM-DD]")
    try:
        location_id = int(argv[1])
    except ValueError:
        sys.exit(f"error: LOCATION_ID must be a number, got {argv[1]!r}")

    film_filter = None
    date = None
    i = 2
    while i < len(argv):
        if argv[i] == "--film" and i + 1 < len(argv):
            film_filter = argv[i + 1]; i += 2
        elif argv[i] == "--date" and i + 1 < len(argv):
            date = argv[i + 1]; i += 2
        else:
            i += 1
    return location_id, film_filter, date


def fetch_films(location_id, date):
    """Return {film_id: {"name": str, "experiences": [str, ...]}}."""
    data = get_showtimes(location_id, date)
    films = {}
    for _, movie, exp, _sess in iter_sessions(data):
        fid = movie.get("id")
        if fid is None:
            continue
        entry = films.setdefault(
            str(fid),
            {"name": movie.get("name", "?"), "experiences": []})
        for t in exp.get("experienceTypes", []):
            if t not in entry["experiences"]:
                entry["experiences"].append(t)
    return films


def main():
    location_id, film_filter, date = parse_args(sys.argv)

    try:
        if date is None:
            dates = get_dates(location_id)
            if not dates:
                sys.exit(f"error: no bookable dates for theatre {location_id}")
            date = dates[0][:10]
        elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            sys.exit(f"error: --date must be YYYY-MM-DD, got {date!r}")

        films = fetch_films(location_id, date)
    except (HTTPError, URLError) as e:
        sys.exit(f"error: Cineplex API request failed ({e}) "
                 f"— check the theatre ID")

    if film_filter:
        needle = film_filter.lower()
        films = {fid: f for fid, f in films.items()
                 if needle in f["name"].lower()}

    if not films:
        msg = f"No films found at theatre {location_id} on {date}"
        if film_filter:
            msg += f' matching "{film_filter}"'
        print(msg + ".")
        return

    width = max(len(fid) for fid in films)
    print(f"{len(films)} film(s) at theatre {location_id} on {date}:\n")
    for fid in sorted(films, key=lambda k: films[k]["name"].lower()):
        f = films[fid]
        print(f"{fid:>{width}}  {f['name']}")
        exps = ", ".join(f["experiences"]) if f["experiences"] else "—"
        print(f"{'':>{width}}  {exps}")
    print(f"\nThen run e.g.: python3 scan.py {location_id} <FILM_ID> "
          f"--film-name \"<title>\"")


if __name__ == "__main__":
    main()
