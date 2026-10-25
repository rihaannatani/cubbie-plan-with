#!/usr/bin/env python3
"""Find shared free time across several people's schedules.

Stdlib only. Reads a JSON file (or "-" for stdin) and prints plain text:
full-overlap windows first, then "partial" windows where everyone but one
person is free and that person joins late.

Input shape (see assets/sample_input.json):
{
  "timezone": "America/Phoenix",            # optional, default America/Phoenix
  "window": {"start": "2026-10-30T12:00", "end": "2026-11-01T23:00"},
  "min_minutes": 90,                        # optional, default 60
  "day_hours": {"start": "10:00", "end": "23:00"},  # optional, null = any hour
  "people": [
    {"name": "Rihaan", "busy": [{"start": "...", "end": "..."}]},
    {"name": "Anhiti", "free": [{"start": "...", "end": "..."}], "late_join_ok": true}
  ]
}

A person gives either "busy" or "free" intervals (or neither = free all window).
Datetimes without an offset are read in "timezone".

Exit codes: 0 ok (even if nothing overlaps), 2 bad input.
"""

import argparse
import json
import sys
from datetime import datetime, time, timedelta, timezone

DEFAULT_TZ = "America/Phoenix"
DEFAULT_MIN = 60
DEFAULT_DAY_HOURS = {"start": "10:00", "end": "23:00"}
MIN_LATE_JOIN = 30   # late joiner must get at least this many minutes
MIN_HEAD_START = 15  # and arrive at least this much after the others start
MAX_FULL = 12
MAX_PARTIAL = 8


class InputError(Exception):
    pass


def get_tz(name):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        if name == "America/Phoenix":
            return timezone(timedelta(hours=-7), "MST")  # Arizona: no DST
        if name.upper() == "UTC":
            return timezone.utc
        raise InputError(f'Unknown timezone "{name}". Use an IANA name like "America/Phoenix".')


def parse_dt(value, tz, where):
    if not isinstance(value, str):
        raise InputError(f"{where}: expected an ISO datetime string, got {value!r}")
    s = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise InputError(f'{where}: "{value}" is not an ISO datetime (try "2026-10-30T18:00")')
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def parse_hhmm(value, where):
    try:
        h, m = str(value).split(":")
        if h == "24" and m == "00":
            return time(23, 59, 59)
        return time(int(h), int(m))
    except Exception:
        raise InputError(f'{where}: "{value}" should look like "18:30"')


def parse_intervals(items, tz, where):
    if not isinstance(items, list):
        raise InputError(f"{where}: expected a list of {{start, end}} objects")
    out = []
    for i, it in enumerate(items):
        w = f"{where}[{i}]"
        if not isinstance(it, dict) or "start" not in it or "end" not in it:
            raise InputError(f"{w}: each interval needs \"start\" and \"end\"")
        a, b = parse_dt(it["start"], tz, w + ".start"), parse_dt(it["end"], tz, w + ".end")
        if b <= a:
            raise InputError(f"{w}: end ({it['end']}) must be after start ({it['start']})")
        out.append((a, b))
    return out


def merge(intervals):
    out = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def subtract(base, cuts):
    """base and cuts are merged, sorted lists. Returns base minus cuts."""
    out = []
    for a, b in base:
        cur = a
        for c, d in cuts:
            if d <= cur or c >= b:
                continue
            if c > cur:
                out.append((cur, c))
            cur = max(cur, d)
            if cur >= b:
                break
        if cur < b:
            out.append((cur, b))
    return out


def intersect(xs, ys):
    out, i, j = [], 0, 0
    while i < len(xs) and j < len(ys):
        a, b = max(xs[i][0], ys[j][0]), min(xs[i][1], ys[j][1])
        if a < b:
            out.append((a, b))
        if xs[i][1] < ys[j][1]:
            i += 1
        else:
            j += 1
    return out


def allowed_hours(start, end, day_hours, tz):
    """The parts of [start, end) that fall inside the daily hours."""
    if not day_hours:
        return [(start, end)]
    h0, h1 = day_hours
    out = []
    day = start.date() - timedelta(days=1)
    while day <= end.date():
        a = datetime.combine(day, h0, tzinfo=tz)
        b = datetime.combine(day, h1, tzinfo=tz) if h1 > h0 else datetime.combine(day + timedelta(days=1), h1, tzinfo=tz)
        a, b = max(a, start), min(b, end)
        if a < b:
            out.append((a, b))
        day += timedelta(days=1)
    return merge(out)


def load(data):
    if not isinstance(data, dict):
        raise InputError("Top level must be a JSON object with \"window\" and \"people\".")
    tz = get_tz(data.get("timezone") or DEFAULT_TZ)
    win = data.get("window")
    if not isinstance(win, dict):
        raise InputError('Missing "window": {"start": ..., "end": ...} (the range to search).')
    ws, we = parse_dt(win.get("start"), tz, "window.start"), parse_dt(win.get("end"), tz, "window.end")
    if we <= ws:
        raise InputError("window.end must be after window.start")
    if we - ws > timedelta(days=31):
        raise InputError("window is longer than 31 days; search a shorter range")
    try:
        min_minutes = int(data.get("min_minutes", DEFAULT_MIN))
    except (TypeError, ValueError):
        raise InputError("min_minutes must be a whole number of minutes")
    if min_minutes < 1:
        raise InputError("min_minutes must be at least 1")
    dh = data.get("day_hours", DEFAULT_DAY_HOURS)
    day_hours = None
    if dh:
        if not isinstance(dh, dict):
            raise InputError('day_hours must be {"start": "10:00", "end": "23:00"} or null')
        day_hours = (parse_hhmm(dh.get("start", "00:00"), "day_hours.start"),
                     parse_hhmm(dh.get("end", "24:00"), "day_hours.end"))
    people = data.get("people")
    if not isinstance(people, list) or len(people) < 2:
        raise InputError('"people" must list at least 2 people.')
    base = allowed_hours(ws, we, day_hours, tz)
    seen, parsed = set(), []
    for i, p in enumerate(people):
        if not isinstance(p, dict) or not str(p.get("name", "")).strip():
            raise InputError(f"people[{i}]: each person needs a \"name\"")
        name = str(p["name"]).strip()
        if name.lower() in seen:
            raise InputError(f'Two people are named "{name}"; names must be unique.')
        seen.add(name.lower())
        where = f"people[{i}] ({name})"
        if "busy" in p and "free" in p:
            raise InputError(f"{where}: give either \"busy\" or \"free\", not both")
        if "free" in p:
            free = intersect(base, merge(parse_intervals(p["free"], tz, where + ".free")))
        else:
            free = subtract(base, merge(parse_intervals(p.get("busy", []), tz, where + ".busy")))
        parsed.append({"name": name, "free": free, "late_join_ok": bool(p.get("late_join_ok", True))})
    return tz, (ws, we), timedelta(minutes=min_minutes), parsed


def compute(tz, min_len, people):
    full = people[0]["free"]
    for p in people[1:]:
        full = intersect(full, p["free"])
    full = [w for w in full if w[1] - w[0] >= min_len]

    partial = []
    for k, late in enumerate(people):
        if not late["late_join_ok"]:
            continue
        others = [p for j, p in enumerate(people) if j != k]
        o = others[0]["free"]
        for p in others[1:]:
            o = intersect(o, p["free"])
        for s, e in o:
            if e - s < min_len:
                continue
            for a, b in intersect([(s, e)], late["free"]):
                if a - s >= timedelta(minutes=MIN_HEAD_START) and b - a >= timedelta(minutes=MIN_LATE_JOIN):
                    partial.append({"late": late["name"], "start": s, "arrive": a, "end": b, "group_end": e})
                    break  # first arrival in this window is the useful one
    partial.sort(key=lambda x: (x["start"], x["arrive"]))
    return full, partial


def fmt_time(dt):
    return dt.strftime("%I:%M%p").lstrip("0").lower().replace(":00", "")


def fmt_day(dt):
    return dt.strftime("%a %b ") + str(dt.day)


def fmt_span(a, b):
    if a.date() == b.date():
        return f"{fmt_day(a)}, {fmt_time(a)}-{fmt_time(b)}"
    return f"{fmt_day(a)} {fmt_time(a)} - {fmt_day(b)} {fmt_time(b)}"


def fmt_len(td):
    m = int(td.total_seconds() // 60)
    h, m = divmod(m, 60)
    return (f"{h}h" if h else "") + (f"{m:02d}m" if h and m else (f"{m}m" if m else ""))


def render_text(window, min_len, people, full, partial):
    names = ", ".join(p["name"] for p in people)
    lines = [f"People: {names}",
             f"Searched: {fmt_span(*window)} (min {fmt_len(min_len)})", ""]
    if full:
        lines.append(f"EVERYONE FREE ({len(full)}):")
        for a, b in full[:MAX_FULL]:
            lines.append(f"- {fmt_span(a, b)} ({fmt_len(b - a)})")
        if len(full) > MAX_FULL:
            lines.append(f"- ...and {len(full) - MAX_FULL} more")
    else:
        lines.append("EVERYONE FREE: none")
    lines.append("")
    if partial:
        lines.append(f"ONE PERSON JOINS LATE ({len(partial)}):")
        for x in partial[:MAX_PARTIAL]:
            lines.append(f"- {fmt_span(x['start'], x['group_end'])}: others start {fmt_time(x['start'])}, "
                         f"{x['late']} arrives {fmt_time(x['arrive'])} (gets {fmt_len(x['end'] - x['arrive'])})")
        if len(partial) > MAX_PARTIAL:
            lines.append(f"- ...and {len(partial) - MAX_PARTIAL} more")
    else:
        lines.append("ONE PERSON JOINS LATE: none")
    if not full and not partial:
        lines += ["", "NO_OVERLAP: nothing fits. Try a longer search window, a shorter min length, or ask who can move something."]
    return "\n".join(lines)


def render_json(full, partial):
    iso = lambda d: d.isoformat()
    return json.dumps({
        "full": [{"start": iso(a), "end": iso(b), "minutes": int((b - a).total_seconds() // 60)} for a, b in full],
        "partial": [{"late": x["late"], "start": iso(x["start"]), "arrive": iso(x["arrive"]),
                     "end": iso(x["end"]), "group_end": iso(x["group_end"])} for x in partial],
    }, indent=1)


def run(data, as_json=False):
    tz, window, min_len, people = load(data)
    full, partial = compute(tz, min_len, people)
    return render_json(full, partial) if as_json else render_text(window, min_len, people, full, partial)


def selftest():
    def case(people, **kw):
        d = {"window": {"start": "2026-10-30T12:00", "end": "2026-10-30T23:00"}, "min_minutes": 60,
             "day_hours": None, "people": people}
        d.update(kw)
        tz, window, min_len, ps = load(d)
        return compute(tz, min_len, ps)

    # Two people, simple overlap: A busy 12-15, B busy 17-19 -> 15-17 and 19-23
    full, _ = case([{"name": "A", "busy": [{"start": "2026-10-30T12:00", "end": "2026-10-30T15:00"}]},
                    {"name": "B", "busy": [{"start": "2026-10-30T17:00", "end": "2026-10-30T19:00"}]}])
    assert [(a.hour, b.hour) for a, b in full] == [(15, 17), (19, 23)], full

    # Overlapping busy blocks merge; free-interval input works; min length filters
    full, _ = case([{"name": "A", "busy": [{"start": "2026-10-30T12:00", "end": "2026-10-30T14:00"},
                                           {"start": "2026-10-30T13:30", "end": "2026-10-30T16:00"}]},
                    {"name": "B", "free": [{"start": "2026-10-30T15:00", "end": "2026-10-30T16:30"},
                                           {"start": "2026-10-30T18:00", "end": "2026-10-30T21:00"}]}])
    assert [(a.hour, a.minute, b.hour) for a, b in full] == [(18, 0, 21)], full  # 16:00-16:30 is too short

    # Late joiner: C in class until 18:00; A and B free from 16:00
    full, partial = case([{"name": "A", "busy": [{"start": "2026-10-30T12:00", "end": "2026-10-30T16:00"}]},
                          {"name": "B", "busy": [{"start": "2026-10-30T12:00", "end": "2026-10-30T16:00"}]},
                          {"name": "C", "busy": [{"start": "2026-10-30T12:00", "end": "2026-10-30T18:00"}]}])
    assert [(a.hour, b.hour) for a, b in full] == [(18, 23)], full
    assert any(p["late"] == "C" and p["start"].hour == 16 and p["arrive"].hour == 18 for p in partial), partial
    # ...but not if C opted out
    _, partial = case([{"name": "A", "busy": [{"start": "2026-10-30T12:00", "end": "2026-10-30T16:00"}]},
                       {"name": "B", "busy": [{"start": "2026-10-30T12:00", "end": "2026-10-30T16:00"}]},
                       {"name": "C", "late_join_ok": False,
                        "busy": [{"start": "2026-10-30T12:00", "end": "2026-10-30T18:00"}]}])
    assert not any(p["late"] == "C" for p in partial), partial

    # Timezones: UTC busy 01:00Z-03:00Z on Oct 31 = 6-8pm Phoenix on Oct 30
    full, _ = case([{"name": "A", "busy": [{"start": "2026-10-31T01:00Z", "end": "2026-10-31T03:00Z"}]},
                    {"name": "B"}])
    assert [(a.hour, b.hour) for a, b in full] == [(12, 18), (20, 23)], full

    # day_hours clips to evenings across several days
    tz, window, min_len, ps = load({"window": {"start": "2026-10-30T00:00", "end": "2026-11-01T23:59"},
                                    "day_hours": {"start": "18:00", "end": "22:00"},
                                    "people": [{"name": "A"}, {"name": "B"}]})
    full, _ = compute(tz, min_len, ps)
    assert len(full) == 3 and all(a.hour == 18 and b.hour == 22 for a, b in full), full

    # No overlap prints the marker
    out = run({"window": {"start": "2026-10-30T12:00", "end": "2026-10-30T14:00"}, "day_hours": None,
               "people": [{"name": "A", "busy": [{"start": "2026-10-30T12:00", "end": "2026-10-30T13:00"}]},
                          {"name": "B", "busy": [{"start": "2026-10-30T13:00", "end": "2026-10-30T14:00"}]}]})
    assert "NO_OVERLAP" in out, out

    # Validation errors are readable
    for bad, needle in [({}, "window"),
                        ({"window": {"start": "2026-10-30T12:00", "end": "2026-10-30T14:00"}, "people": [{"name": "A"}]}, "at least 2"),
                        ({"window": {"start": "2026-10-30T12:00", "end": "2026-10-30T14:00"},
                          "people": [{"name": "A", "busy": [{"start": "nope", "end": "2026-10-30T13:00"}]}, {"name": "B"}]}, "not an ISO"),
                        ({"window": {"start": "2026-10-30T12:00", "end": "2026-10-30T14:00"},
                          "people": [{"name": "A", "busy": [{"start": "2026-10-30T13:00", "end": "2026-10-30T12:00"}]}, {"name": "B"}]}, "must be after")]:
        try:
            load(bad)
            raise AssertionError(f"expected error for {bad}")
        except InputError as e:
            assert needle in str(e), (needle, str(e))

    print("selftest ok (8 checks)")


def main():
    ap = argparse.ArgumentParser(description="Find shared free time across people's schedules.")
    ap.add_argument("--input", help='JSON file, or "-" for stdin')
    ap.add_argument("--json", action="store_true", help="print JSON instead of text")
    ap.add_argument("--selftest", action="store_true", help="run built-in tests")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return 0
    if not args.input:
        print("ERROR: pass --input <file.json> (or --selftest)")
        return 2
    try:
        raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
        data = json.loads(raw)
    except FileNotFoundError:
        print(f"ERROR: input file not found: {args.input}")
        return 2
    except json.JSONDecodeError as e:
        print(f"ERROR: input is not valid JSON (line {e.lineno}, col {e.colno}): {e.msg}")
        return 2
    try:
        print(run(data, args.json))
    except InputError as e:
        print(f"ERROR: {e}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
