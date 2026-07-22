#!/usr/bin/env python3
"""Generate a scrollable HTML page of seat maps for a Cineplex movie.

Usage:
  python3 gen_seatmaps.py LOCATION_ID FILM_ID \\
      --film-name "The Odyssey" --theatre-name "Cinema Banque Scotia Montreal" \\
      --experience IMAX -o /tmp/seats.html

Defaults to The Odyssey @ Cinema Banque Scotia (9406 / 37617 / IMAX).

Output: self-contained HTML with one SVG seat map card per showtime,
grouped by day.  Each map highlights the best centred and furthest-back
3-seat blocks.
"""
import sys
import json
import html as _html
from collections import defaultdict, Counter

from cineplex_api import (
    get_dates, get_showtimes, iter_sessions,
    get_seat_availability, parse_seats,
    get_seat_layout, parse_seat_layout,
    best_centered_triple, best_furthest_triple, wheelchair_seats,
    ROW_TO_LETTER, depth, FRONT_ROWS, DISPLAY_ORDER,
    booking_url,
)

# ---- SVG layout constants ----
CW = 11          # seat width
CH = 9           # seat height
G = 2            # gap between seats
RG = 7           # row gap (vertical)
AISLE_H = 6      # aisle height
SCREEN_H = 20    # screen area height
COLS = 35
OX = 16          # left offset for labels


def render_svg(byrow, highlights, special_seats):
    w = COLS * (CW + G) - G
    y = SCREEN_H + 10
    parts = []
    for item in DISPLAY_ORDER:
        if item is None:
            y += AISLE_H
            continue
        api, letter = item
        cols = byrow.get(api, {})
        for c in range(1, COLS + 1):
            st = cols.get(c)
            x = OX + (c - 1) * (CW + G)
            if st is None:
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{CW}" height="{CH}" '
                    f'rx="1.5" fill="#334155" opacity="0.35"/>')
                continue
            seat_type = special_seats.get((api, c))
            if seat_type == "Wheelchair":
                op = "0.9" if st == "Available" else "0.35"
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{CW}" height="{CH}" '
                    f'rx="1.5" fill="#0284c7" opacity="{op}"/>'
                    f'<text x="{x+CW/2}" y="{y+CH-1.5}" text-anchor="middle" '
                    f'fill="#38bdf8" font-size="6">♿</text>')
                continue
            if seat_type == "Companion":
                fill = "#38bdf8"       # light blue = companion seat
                op = "0.9" if st == "Available" else "0.4"
            else:
                fill = "#4ade80" if st == "Available" else "#ef4444"
                op = "1" if st == "Available" else "0.65"
            stroke = ""
            if (api, c) in highlights:
                stroke = ' stroke="#fde047" stroke-width="1.8"'
            parts.append(
                f'<rect x="{x}" y="{y}" width="{CW}" height="{CH}" '
                f'rx="1.5" fill="{fill}" opacity="{op}"{stroke}/>')
        parts.append(
            f'<text x="{OX-5}" y="{y+CH-1}" text-anchor="end" '
            f'fill="#94a3b8" font-size="7.5">{letter}</text>')
        parts.append(
            f'<text x="{OX+w+5}" y="{y+CH-1}" text-anchor="start" '
            f'fill="#94a3b8" font-size="7.5">{letter}</text>')
        y += CH + RG
    total_h = y + 6
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w+2*OX}" height="{total_h}" '
        f'viewBox="0 0 {w+2*OX} {total_h}">'
        f'<defs>'
        f'<linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="#ec4899"/>'
        f'<stop offset="1" stop-color="#8b5cf6"/>'
        f'</linearGradient></defs>'
        f'<text x="{w/2+OX}" y="14" text-anchor="middle" '
        f'fill="#94a3b8" font-size="9">SCREEN</text>'
        f'<rect x="{OX}" y="2" width="{w}" height="{SCREEN_H-6}" rx="2" '
        f'fill="url(#sg)" opacity="0.3" stroke="url(#sg)" stroke-width="1"/>'
        + "".join(parts) + "</svg>"
    )


def main():
    location_id = int(sys.argv[1]) if len(sys.argv) > 1 else 9406
    film_id = int(sys.argv[2]) if len(sys.argv) > 2 else 37617
    film_name = "The Odyssey"
    theatre_name = "Cinema Banque Scotia Montreal"
    exp_filter = "IMAX"
    out_path = "/tmp/cineplex-seatmaps.html"

    args = sys.argv[3:]
    i = 0
    while i < len(args):
        if args[i] == "--film-name" and i + 1 < len(args):
            film_name = args[i + 1]; i += 2
        elif args[i] == "--theatre-name" and i + 1 < len(args):
            theatre_name = args[i + 1]; i += 2
        elif args[i] == "--experience" and i + 1 < len(args):
            exp_filter = args[i + 1]; i += 2
        elif args[i] == "-o" and i + 1 < len(args):
            out_path = args[i + 1]; i += 2
        else:
            i += 1

    print(f"Fetching {film_name} — {exp_filter} @ {theatre_name} …")

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

    # Fetch seat layout once (auditorium-level: exact Wheelchair/Companion types)
    special_seats = {}
    for ds in sorted(byday):
        if byday[ds]:
            special_seats = parse_seat_layout(
                get_seat_layout(location_id, byday[ds][0]["sid"]))
            break
    if special_seats:
        by_letter = defaultdict(Counter)
        for (r, _c), t in special_seats.items():
            by_letter[ROW_TO_LETTER[r]][t] += 1
        desc = ", ".join(f"{L}: {dict(cnt)}" for L, cnt in sorted(by_letter.items()))
        print(f"  Accessible seats (seat-layout): {desc}")
    else:
        print("  (no wheelchair/companion seats in layout)")

    cards_by_day = {}
    stats = {"days": 0, "shows": 0, "days_centered": 0, "days_further": 0}

    for ds in sorted(byday):
        stats["days"] += 1
        cards = []
        day_centered = day_further = False

        for sh in byday[ds]:
            sa = get_seat_availability(location_id, sh["sid"])
            byrow = parse_seats(sa["seatAvailabilities"])
            stats["shows"] += 1
            free = sum(1 for v in sa["seatAvailabilities"].values()
                       if v == "Available")

            skip = wheelchair_seats(special_seats)
            bc = best_centered_triple(byrow, skip_seats=skip)
            bf = best_furthest_triple(byrow, skip_seats=skip)
            highlights = set()
            notes = []

            if bc and bc[2] <= 6:  # off-centre <= 6
                api, s, off, _ = bc
                L = ROW_TO_LETTER[api]
                for c in (s, s + 1, s + 2):
                    highlights.add((api, c))
                notes.append(
                    f'<b>centred:</b> {L}{s}&#8211;{L}{s+2} ({off:.0f} off)')
                if off <= 4:
                    day_centered = True

            if bf:
                api, s, off, _ = bf
                L = ROW_TO_LETTER[api]
                if not bc or api != bc[0] or s != bc[1]:
                    for c in (s, s + 1, s + 2):
                        highlights.add((api, c))
                    notes.append(
                        f'<b>furthest:</b> {L}{s}&#8211;{L}{s+2} ({off:.0f} off)')
                if depth(api) >= 5:
                    day_further = True

            if not notes:
                notes.append('<span class=muted>no 3-together behind row C</span>')

            svg = render_svg(byrow, highlights, special_seats)
            url = booking_url(location_id, sh["sid"])
            cards.append(
                f'<div class=card>'
                f'<div class=chead><span class=time>{sh["time"]}</span>'
                f'<span class=left>{free} free</span></div>'
                f'<div class=notes>{" &nbsp;|&nbsp; ".join(notes)}</div>'
                f'{svg}'
                f'<a class=book href="{url}" target=_blank>book &#8594; sid {sh["sid"]}</a>'
                f'</div>'
            )

        if day_centered:
            stats["days_centered"] += 1
        if day_further:
            stats["days_further"] += 1
        cards_by_day[ds] = (cards, day_centered, day_further)

    # ---- assemble HTML ----
    sections = []
    for ds in sorted(cards_by_day):
        cards, hc, hf = cards_by_day[ds]
        badges = ""
        if hc:
            badges += '<span class="badge b-c">centred &#10003;</span>'
        if hf:
            badges += '<span class="badge b-f">further &#10003;</span>'
        sections.append(
            f'<section><h3>{ds} '
            f'<span class=daycount>({len(cards)} showtimes)</span> {badges}'
            f'</h3><div class=grid>{"".join(cards)}</div></section>'
        )

    page = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{film_name} &ndash; {exp_filter} seat maps</title>
<style>
 body{{margin:0;background:#0f0f1e;color:#e5e7eb;font:13px Inter,system-ui,sans-serif;}}
 header{{position:sticky;top:0;z-index:5;background:#171730;padding:12px 18px;border-bottom:1px solid #2a2a4a;box-shadow:0 2px 8px #0006;}}
 header h1{{margin:0 0 6px;font-size:16px;font-weight:600;}}
 .legend{{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:#cbd5e1;}}
 .legend span{{display:inline-flex;align-items:center;gap:5px;}}
 .sq{{width:12px;height:11px;border-radius:2px;display:inline-block;}}
 .stats{{margin-top:6px;font-size:12px;color:#94a3b8;}}
 main{{padding:16px 18px 60px;}}
 section{{margin-bottom:26px;}}
 h3{{font-size:14px;font-weight:600;margin:0 0 10px;border-left:3px solid #4ade80;padding-left:8px;}}
 .daycount{{color:#94a3b8;font-weight:400;font-size:12px;}}
 .badge{{font-size:10px;padding:1px 7px;border-radius:10px;margin-left:6px;vertical-align:middle;}}
 .b-c{{background:#166534;color:#bbf7d0;}} .b-f{{background:#1e3a8a;color:#bfdbfe;}}
 .grid{{display:flex;flex-wrap:wrap;gap:12px;}}
 .card{{background:#1a1a30;border:1px solid #2a2a4a;border-radius:8px;padding:8px;}}
 .chead{{display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;}}
 .time{{font-weight:600;font-size:14px;}} .left{{font-size:11px;color:#4ade80;}}
 .notes{{font-size:10.5px;color:#cbd5e1;margin-bottom:4px;min-height:14px;}}
 .notes b{{color:#fde047;font-weight:600;}} .muted{{color:#6b7280;}}
 .book{{display:block;margin-top:4px;font-size:10px;color:#93c5fd;text-decoration:none;}}
 .book:hover{{text-decoration:underline;}}
</style></head><body>
<header>
 <h1>{_html.escape(film_name)} &mdash; {_html.escape(exp_filter)} &mdash; {_html.escape(theatre_name)} ({location_id})</h1>
 <div class=legend>
  <span><span class=sq style=background:#4ade80></span>Available</span>
   <span><span class=sq style=background:#38bdf8;opacity:.9></span>Companion seat</span>
   <span><span class=sq style="background:#0284c7;opacity:.9;text-align:center;font-size:7px;color:#38bdf8;">♿</span>Wheelchair space</span>
  <span><span class=sq style="background:#ef4444;opacity:.65"></span>Occupied</span>
  <span><span class=sq style="background:#334155;opacity:.35"></span>No seat</span>
  <span><span class=sq style="background:#4ade80;outline:2px solid #fde047"></span>Suggested trio</span>
  <span>SCREEN at top &middot; rows A(front)&ndash;K(back) &middot; aisle E/F</span>
 </div>
 <div class=stats>
  {stats['days']} days &middot; {stats['shows']} showtimes &middot;
  {stats['days_centered']}/{stats['days']} days with a centred trio &middot;
  {stats['days_further']}/{stats['days']} days with a trio in the back block (F&ndash;K)
 </div>
</header>
<main>{"".join(sections)}</main>
</body></html>"""

    with open(out_path, "w") as f:
        f.write(page)
    print(f"Wrote {out_path}")
    print(f"{stats['days']} days, {stats['shows']} showtimes.")


if __name__ == "__main__":
    main()
