#!/usr/bin/env python3
"""List Sun Devil Central (ASU clubs) events that fit the group's free windows.

Stdlib only. Downloads the public iCal feed (no ASU login needed), caches it for
an hour, and prints a short plain-text list.

  python3 scripts/sdc_events.py --from 2026-10-30T17:00 --to 2026-10-30T23:00
  python3 scripts/sdc_events.py --windows overlap.json --keywords "boba,games,food"
  python3 scripts/sdc_events.py --sample --from 2026-10-30T00:00 --to 2026-11-01T23:59

--windows takes the output of `overlap.py --json` and keeps events that start
inside a full or partial window and end before it does.

Exit codes: 0 ok (even if nothing matches), 2 bad arguments, 4 feed unreachable.
"""

import argparse
import json
import os
import quopri
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

FEED = "https://sundevilcentral.eoss.asu.edu/ical/arizonau/ical_arizonau.ics"
PHX = timezone(timedelta(hours=-7), "MST")  # Arizona: no DST
CACHE_SECONDS = 3600
HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "..", "assets", "sample_events.ics")
# Club business that rarely makes a good hangout; use --types to override.
SKIP_TYPES = {"meeting", "training", "orientation", "general body meeting", "info session", "information session"}


def fetch(use_sample):
    if use_sample:
        return open(SAMPLE, encoding="utf-8").read()
    cache_dir = os.environ.get("SKILL_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".cache", "plan-with")
    os.makedirs(cache_dir, exist_ok=True)
    cache = os.path.join(cache_dir, "sdc_feed.ics")
    if os.path.exists(cache) and time.time() - os.path.getmtime(cache) < CACHE_SECONDS:
        return open(cache, encoding="utf-8").read()
    try:
        req = urllib.request.Request(FEED, headers={"User-Agent": "plan-with-cubbie-skill"})
        with urllib.request.urlopen(req, timeout=60) as r:
            text = r.read().decode("utf-8", "replace")
    except Exception as e:
        if os.path.exists(cache):
            return open(cache, encoding="utf-8").read()  # stale beats nothing
        print(f"ERROR: could not reach Sun Devil Central's feed ({e.__class__.__name__}). Use ASU events or web search instead.")
        sys.exit(4)
    with open(cache, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def unescape(v):
    return v.replace("\\n", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()


def parse(text):
    text = re.sub(r"\r?\n[ \t]", "", text)  # unfold continuation lines
    events, cur = [], None
    for line in text.splitlines():
        if line == "BEGIN:VEVENT":
            cur = {"types": []}
        elif line == "END:VEVENT":
            if cur and "start" in cur:
                events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            key, val = line.split(":", 1)
            name, params = key.split(";")[0], key
            if "ENCODING=QUOTED-PRINTABLE" in params:
                val = quopri.decodestring(val.encode()).decode("utf-8", "replace")
            if name in ("DTSTART", "DTEND"):
                dt = parse_ics_dt(val)
                if dt:
                    cur["start" if name == "DTSTART" else "end"] = dt
            elif name == "SUMMARY":
                cur["title"] = unescape(val)
            elif name == "LOCATION":
                cur["location"] = unescape(val)
            elif name == "URL":
                cur["url"] = val.strip()
            elif name == "DESCRIPTION":
                cur["desc"] = unescape(val.split("\\n---")[0])
            elif name == "ORGANIZER":
                m = re.search(r'CN="?([^":;]+)', key)
                cur["org"] = m.group(1).strip() if m else ""
            elif name == "CATEGORIES" and "event_type" in params:
                cur["types"].append(val.strip())
    return events


def parse_ics_dt(v):
    v = v.strip()
    try:
        if v.endswith("Z"):
            return datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(PHX)
        if "T" in v:
            return datetime.strptime(v, "%Y%m%dT%H%M%S").replace(tzinfo=PHX)
        return datetime.strptime(v, "%Y%m%d").replace(tzinfo=PHX)
    except ValueError:
        return None


def parse_arg_dt(v, flag):
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        print(f'ERROR: {flag} "{v}" is not an ISO datetime (try 2026-10-30T18:00)')
        sys.exit(2)
    return (dt if dt.tzinfo else dt.replace(tzinfo=PHX)).astimezone(PHX)


def load_windows(path):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: could not read --windows file ({e}). Pass the output of overlap.py --json.")
        sys.exit(2)
    out = [(parse_arg_dt(w["start"], "--windows"), parse_arg_dt(w["end"], "--windows")) for w in data.get("full", [])]
    out += [(parse_arg_dt(w["start"], "--windows"), parse_arg_dt(w["group_end"], "--windows")) for w in data.get("partial", [])]
    return out


def fmt(dt):
    return dt.strftime("%I:%M%p").lstrip("0").lower().replace(":00", "")


def main():
    ap = argparse.ArgumentParser(description="Filter Sun Devil Central events.")
    ap.add_argument("--from", dest="start")
    ap.add_argument("--to", dest="end")
    ap.add_argument("--windows", help="overlap.py --json output file")
    ap.add_argument("--keywords", default="", help="comma-separated; match title, club or description")
    ap.add_argument("--types", default="", help="comma-separated event types to keep (e.g. Social,Cultural)")
    ap.add_argument("--online", action="store_true", help="include online events")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--sample", action="store_true", help="use the bundled sample feed (no network)")
    a = ap.parse_args()

    if a.windows:
        windows = load_windows(a.windows)
        if not windows:
            print("No windows in the --windows file, so no events can fit. Find shared time first.")
            return 0
    elif a.start and a.end:
        windows = [(parse_arg_dt(a.start, "--from"), parse_arg_dt(a.end, "--to"))]
    else:
        print("ERROR: pass --from and --to, or --windows <overlap.json>")
        return 2

    kws = [k.strip().lower() for k in a.keywords.split(",") if k.strip()]
    keep_types = {t.strip().lower() for t in a.types.split(",") if t.strip()}
    hits = []
    for e in parse(fetch(a.sample)):
        end = e.get("end", e["start"] + timedelta(hours=1))
        if not any(ws <= e["start"] and end <= we for ws, we in windows):
            continue
        types = {t.lower() for t in e["types"]}
        if keep_types and not (types & keep_types):
            continue
        if not keep_types and types and types <= SKIP_TYPES:
            continue
        loc = e.get("location", "")
        if not a.online and "online" in loc.lower():
            continue
        hay = " ".join([e.get("title", ""), e.get("org", ""), e.get("desc", "")]).lower()
        score = sum(k in hay for k in kws)
        if kws and not score:
            continue
        e["end"], e["score"] = end, score
        hits.append(e)

    hits.sort(key=lambda e: (-e["score"], e["start"]))
    if not hits:
        print("NO_MATCHES: no Sun Devil Central events fit those times"
              + (" and keywords" if kws else "") + ". Try ASU events or web search.")
        return 0
    print(f"{len(hits)} Sun Devil Central events fit" + (f" (showing {a.limit})" if len(hits) > a.limit else "") + ":")
    for e in hits[:a.limit]:
        loc = e.get("location", "")
        if not loc or "sign in" in loc.lower():
            loc = "location hidden (sign in to Sun Devil Central to see it)"
        desc = e.get("desc", "")
        desc = (desc[:90] + "...") if len(desc) > 90 else desc
        print(f"- {e['start'].strftime('%a %b')} {e['start'].day}, {fmt(e['start'])}-{fmt(e['end'])} | {e.get('title', '?')}"
              f" | {e.get('org', '')} | {', '.join(e['types']) or 'event'} | {loc}"
              + (f" | {desc}" if desc else "") + f"\n  {e.get('url', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
