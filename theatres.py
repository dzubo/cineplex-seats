#!/usr/bin/env python3
"""List Cineplex theatres with their LOCATION_IDs.

Usage:
  python3 theatres.py [--search TEXT]

Without --search, prints every theatre in Canada.
"""
import sys
import unicodedata

from cineplex_api import get_theatres


def _fold(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower())
                   if not unicodedata.combining(c))


def main():
    args = sys.argv[1:]
    search = None
    i = 0
    while i < len(args):
        if args[i] == "--search" and i + 1 < len(args):
            search = args[i + 1].lower(); i += 2
        else:
            i += 1

    theatres = get_theatres()
    if search:
        search = _fold(search)
        theatres = [t for t in theatres if search in
                    _fold(f"{t['name']} {t['city']} {t['province']}")]

    for t in sorted(theatres, key=lambda t: t["id"]):
        where = f"{t['city']}, {t['province']}" if t['province'] else t['city']
        print(f"{t['id']:>6}  {t['name']}  ({where})")

    print(f"\n{len(theatres)} theatre(s)."
          + (f" Then run e.g.: python3 find.py <ID>" if search else ""))


if __name__ == "__main__":
    main()
