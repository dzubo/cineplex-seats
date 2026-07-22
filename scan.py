#!/usr/bin/env python3
"""Print a per-day report of seat availability for a Cineplex movie.

Usage:
  python3 scan.py LOCATION_ID FILM_ID [--film-name "The Odyssey"] [--experience IMAX]

Defaults to Cinema Banque Scotia Montreal (9406), The Odyssey (37617), IMAX.
"""
import sys
import json
from collections import defaultdict

from cineplex_api import (
    get_dates, get_showtimes, iter_sessions,
    get_seat_availability, parse_seats,
    get_seat_layout, parse_seat_layout,
    best_centered_triple, best_furthest_triple, wheelchair_seats,
    ROW_TO_LETTER, depth, CENTRE_COL,
)


def main():
    location_id = int(sys.argv[1]) if len(sys.argv) > 1 else 9406
    film_id = int(sys.argv[2]) if len(sys.argv) > 2 else 37617
    film_name = "The Odyssey"
    exp_filter = "IMAX"

    # parse optional flags
    args = sys.argv[3:]
    i = 0
    while i < len(args):
        if args[i] == "--film-name" and i + 1 < len(args):
            film_name = args[i + 1]; i += 2
        elif args[i] == "--experience" and i + 1 < len(args):
            exp_filter = args[i + 1]; i += 2
        else:
            i += 1

    print(f"{film_name} — {exp_filter} @ theatre {location_id}")
    print(f"'Centered' = 3 seats together within ~4 of centre, "
          f"not in front rows A–C.")
    print()

    dates = get_dates(location_id, film_id)
    byday = defaultdict(list)

    for d in dates:
        ds = d[:10]
        data = get_showtimes(location_id, ds, film_id)
        for date_str, movie, exp, sess in iter_sessions(
                data, film_id, exp_filter):
            byday[date_str].append({
                "time": sess.get("showStartDateTime", "")[11:16],
                "sid": sess["vistaSessionId"],
                "left": sess.get("seatsRemaining", 0),
            })

    # Fetch seat layout once (auditorium-level: exact Wheelchair/Companion seats)
    special = {}
    for ds in sorted(byday):
        if byday[ds]:
            special = parse_seat_layout(
                get_seat_layout(location_id, byday[ds][0]["sid"]))
            break

    if special:
        def fmt(t):
            seats = sorted((ROW_TO_LETTER[r], c)
                           for (r, c), st in special.items() if st == t)
            return ", ".join(f"{L} col {c}" for L, c in seats) or "—"
        print(f"  accessible seats (seat-layout): "
              f"wheelchair [{fmt('Wheelchair')}]; companion [{fmt('Companion')}]")
        print(f"  note: 'Available' counts may include those accessible-only seats")

    hdr = (f"{'date':10} {'shows':>5} {'seats':>7} "
           f"{'centered?':>9}  best centered triples  │  furthest-back triple")
    print(hdr)
    print("-" * len(hdr))

    grand_shows = 0
    grand_days_centered = 0
    grand_days_further = 0

    for ds in sorted(byday):
        shows = byday[ds]
        grand_shows += len(shows)
        total_left = 0
        best_c = None   # (score, api, start, off, depth)
        best_f = None   # (score, api, start, off, depth)
        n_centered = 0
        n_further = 0

        for sh in shows:
            sa = get_seat_availability(location_id, sh["sid"])
            byrow = parse_seats(sa["seatAvailabilities"])
            total_left += sum(
                1 for v in sa["seatAvailabilities"].values() if v == "Available"
            )

            skip = wheelchair_seats(special)
            bc = best_centered_triple(byrow, skip_seats=skip)
            if bc:
                _, _, off, d = bc
                if off <= 4:
                    n_centered += 1
                cand_c = (off + abs(d - 5) * 2, bc[0], bc[1], off, d)
                if best_c is None or cand_c[0] < best_c[0]:
                    best_c = cand_c

            bf = best_furthest_triple(byrow, skip_seats=skip)
            if bf:
                _, _, off, _ = bf
                if bf[0] in (6, 5, 4, 3, 2, 1):  # F or deeper
                    n_further += 1
                cand_f = (-bf[3], bf[0], bf[1], bf[2], bf[3])
                if best_f is None or cand_f[:2] < best_f[:2]:
                    best_f = cand_f

        if n_centered > 0:
            grand_days_centered += 1
        if n_further > 0:
            grand_days_further += 1

        def fmt_triple(b):
            if b is None:
                return "—"
            _, api, start, off, _ = b
            L = ROW_TO_LETTER[api]
            return f"{L}{start}–{L}{start+2} ({off:.0f} off)"

        c_str = fmt_triple(best_c) if best_c else "—"
        f_str = fmt_triple(best_f) if best_f else "—"

        print(f"{ds:10} {len(shows):>5} {total_left:>7} "
              f"{n_centered:>2}/{len(shows):<2}     {c_str:<20}  │  {f_str}")

    print()
    print(f"Overall: {len(byday)} days, {grand_shows} showtimes.")
    print(f"Days with >=1 centered mid/back 3-block: "
          f"{grand_days_centered}/{len(byday)}.")
    print(f"Days with >=1 back-block (F–K) 3-block: "
          f"{grand_days_further}/{len(byday)}.")


if __name__ == "__main__":
    main()
