# plan-with

A Cubbie Skill that turns "we should hang out" into three plans that work for everyone. Each plan fits
everyone's free time, fits each person's budget, and gives each person a real way there and home.

- Finds overlapping free time from your Google Calendar and your friends' screenshots or pasted times,
  including "the rest of you start, Anhiti meets you after class" plans.
- Pulls events from Sun Devil Central's public feed (no login needed), ASU Events and the web.
- Travel-aware: car or no car, Valley Metro light rail, buses and ASU shuttles, a return trip that still runs
  when the night ends, carpool pickups on the way, and no plan where the Uber-averse friend has to Uber alone.
- Shows one total cost per person, travel included.
- Learns your group: tell it "that was fun" or "kinda mid" and it remembers why.

It never texts your friends. It drafts the message, and you send it.

## Install

Text Cubbie the link to this folder:

```
https://github.com/rihaannatani/cubbie-plan-with/tree/main/plan-with
```

and reply yes to install.

## Try it

- "plan something with Anhiti this week"
- "what can we do Friday night, me Maya and Jay, none of us have a car"
- "Jay hates Ubering and is in class till 6 Fri"
- "that was kinda mid"

## Files

- `SKILL.md`: the instructions Cubbie follows
- `references/travel.md`: transit, carpool and cost rules
- `scripts/overlap.py`: shared free time (stdlib only). `python3 scripts/overlap.py --selftest`
- `scripts/sdc_events.py`: Sun Devil Central events in a time window (stdlib only). Add `--sample` to run offline
- `assets/`: sample inputs for both scripts
