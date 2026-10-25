---
name: plan-with
description: Plans a hangout with friends that actually works for everyone, matching free time, budget, vibe and how each person gets there and back (car, Valley Metro light rail and bus, ASU shuttles, carpools). Use when the student says "plan something with <friend>", "what can we do Friday", "find something for me and my friends", or asks for a hangout, outing or group plan around ASU.
license: Apache-2.0
metadata:
  author: rihaan
  version: "1.0"
---

# Plan With

Turns "we should hang out" into three plans that work: everyone is free, it fits each budget, and each
person has a real way there and home. Built for ASU (Tempe, Downtown Phoenix, Poly, West Valley); the travel
rules work anywhere, the event sources are ASU-specific.

## When to use

- "plan something with Anhiti this week"
- "what can we do Friday night, me Maya and Jay"
- "find something for me and my friends, none of us have a car"
- "that was fun" / "kinda mid" after a hangout this Skill planned (see Step 9)

Not for study sessions or study plans; Cubbie's built-in `study-plan-builder` handles those.

## Ground rules

- Cubbie texts only the student. Never message the friends. Their info comes through the student: a screenshot,
  pasted times, or answers the student relays. Draft messages for the student to send.
- Ask before adding anything to Google Calendar, buying tickets or RSVPing. Hand the browser to the student for
  any payment.
- Ask at most one short message of questions at a time, with a default the student can accept with "yes".

## Replies

Short, plain text, no Markdown symbols. One idea per message. Links on their own line. Each plan is its own
text. Use times like "Fri 7pm", money like "$12", and people's first names.

## Steps

### 1. Who, when, roughly what

From the student's message, work out the people (the student plus friends), the date range (default: the next
7 days), and any vibe ("chill", "food", "outdoors", "cheap"). If no friend is named, ask "Who's coming?".

### 2. Load each person's profile from memory

Memory holds one profile per person, saved under "plan-with profile: <name>":

- has a car (yes/no), and seats if yes
- home area (dorm or neighborhood, e.g. "Tooker House", "Downtown Phoenix", "Mesa near Dobson")
- budget per hangout (dollars, including travel)
- likes and dislikes (food, activities, "hates loud places")
- Uber OK (yes/no)
- usual class or work times, if the student shared them

Ask only for what's missing, all in one text. Example:

```
Quick q's so I plan this right:
- Does Anhiti have a car?
- Where do they live, roughly?
- Budget for each of you? ($20?)
- Anyone not into Ubering?
```

Use "they" for a friend until the student says otherwise. After the student answers, ask "Save these for next
time?" and save on yes. If the student says someone "isn't feeling great today" or similar, keep that for
this plan only: low energy, close by, easy to leave early. Don't save it.

### 3. Get everyone's free time

- The student: read their Google Calendar for the date range (busy blocks). If Google isn't connected, ask
  "When are you free? (e.g. Fri after 4, Sat all day)" and don't push them to connect.
- Friends: ask the student to send a screenshot of the friend's schedule, or paste times ("she's in class till
  6 Friday"). Read screenshots for busy blocks. If the student doesn't know, assume the friend is free
  11am-11pm and say so in the plan ("assuming Jay's free, double check").
- Ask whether a friend who's busy part of the time could meet the group late. Default yes.

### 4. Find shared windows

Write the input JSON to `$SKILL_DATA_DIR/overlap_input.json`, then run from this Skill's folder:

```bash
python3 scripts/overlap.py --input "$SKILL_DATA_DIR/overlap_input.json"
python3 scripts/overlap.py --input "$SKILL_DATA_DIR/overlap_input.json" --json > "$SKILL_DATA_DIR/windows.json"
```

The JSON shape is at the top of `scripts/overlap.py` and in `assets/sample_input.json`: a search `window`, a
`min_minutes` (default 90 for a hangout), `day_hours` (default 11:00-23:00), and one entry per person with
`busy` or `free` intervals (ISO datetimes, Arizona time) and an optional `late_join_ok`.

It prints "EVERYONE FREE" windows and "ONE PERSON JOINS LATE" windows.

- Exit 2 prints `ERROR: ...`: fix the JSON and run again. Don't show the error to the student.
- `NO_OVERLAP`: tell the student nothing lines up, name the closest near-miss, and ask one question that could
  open time up ("Could Maya do Sunday instead?" or "Want me to look at next week?").

### 5. Find things to do

Try these in order and stop when you have about 8 candidates that fit a window:

1. Sun Devil Central (ASU club events), from the public feed, no login:
   ```bash
   python3 scripts/sdc_events.py --windows "$SKILL_DATA_DIR/windows.json" --keywords "<vibe words>"
   ```
   It skips plain club meetings. Its locations are often hidden. For a finalist with a hidden location, open
   its link in the browser. If Sun Devil Central asks for a login, ask the student once to sign in with their
   ASU account (secure login page, or take over the browser for Duo). The login is saved for next time. If
   they'd rather not, say "location TBA, on the event page" and keep going. Exit 4 means the feed is down: skip
   to the next source.
2. ASU's public events calendar: https://asuevents.asu.edu (filter by campus and date, read in the browser or
   with web reading).
3. Web search near the group's area for the vibe: food spots, free events, Mill Ave, Tempe Town Lake, Roosevelt
   Row First Friday, movies, bowling, climbing gyms, hikes (only in daylight, and not in summer afternoon heat).

Drop anything over the lowest budget once travel is added (Step 6), and anything a profile dislikes.

### 6. Check travel for every candidate

Follow `references/travel.md`. In short:

- Look up each person's trip from their home area: driving time for people with cars, transit for everyone else
  (Google Maps transit directions in the browser, or Valley Metro's trip planner at https://www.valleymetro.org).
- No car in the group means transit, walking or ASU shuttles only. The trip home must still be running when the
  event ends: check the last light rail, bus or shuttle time on that day.
- Pair people: a driver whose route passes near a non-driver can pick them up (say so: "Maya grabs Jay on
  the way, +6 min"). Friends who live close can ride transit together.
- Late joiner: "you two take the 6:10 light rail, Anhiti comes straight from class and meets you at 6:40."
- If someone is Uber-averse, drop any plan where they'd be the only one who has to Uber. A shared Uber with
  someone else is OK only if their profile doesn't say "no Uber at all".
- Cost per person = event cost + round trip (transit fare, or a gas share and parking for drivers, split with
  riders if they carpool, or an Uber split).

### 7. Send the top 3

Rank by: everyone can come for the most time, fits every budget, simple travel, matches the vibe and likes.
Send one short intro line, then each plan as its own text:

```
1) Chai & Chill (ASA club), Fri 6-8pm, MU
$4 each with light rail
- You + Maya: light rail from Veterans Way 5:40, back by 8:30
- Anhiti: walks from class, 5 min
https://sundevilcentral.eoss.asu.edu/rsvp?id=414763
```

Then: "Which one? (1/2/3, or 'more')". On "more", send the next 3 or loosen one filter and say which one.

### 8. When the student picks one

1. "Add it to your calendar?" On yes, add an event to their Google Calendar with the place, the travel plan in
   the notes, and the link. If Google isn't connected, offer an .ics file instead.
2. "Want a heads-up when it's time to leave? (5:25pm?)" On yes, set a reminder by text for the student's leave
   time, worded so it makes sense on its own: "plan-with: leave now for Chai & Chill at the MU, light rail
   from Veterans Way 5:40."
3. Draft a message the student can copy and send to the friends, with the what, when, where and each person's
   ride. Don't send it. Say "Here's a text you can send them:" and put the draft in its own message.
4. If it needs tickets or an RSVP, offer to open the page in the browser. The student does any payment.

### 9. Follow-up and learning (only if the student opts in)

Ask after a pick: "Want me to check in tomorrow on how it went?" On yes, schedule a check-in for the next day
around noon: "plan-with: ask how <event> with <names> went yesterday, and why."

When the student replies (or says "that was fun", "kinda mid", anything like that at any time):

1. Ask one short why if they didn't say ("What made it mid, the place or the timing?").
2. Update the relevant profiles in memory: a like or dislike, a budget that was too tight, "light rail at
   night was annoying", a friend who was late. Say in one line what you saved ("Noted: Jay's not into loud bars").

## When something fails

- Google not connected: ask for the student's free times in one text, then carry on.
- A friend's screenshot is unreadable: ask the student to paste the times instead.
- Nothing fits the budget: show the cheapest plan with its real cost and ask if it's OK.
- No transit home late enough: say so and offer an earlier slot, a carpool, or (only if nobody's Uber-averse
  alone) a shared ride home.
- Every source comes back empty: suggest one easy, free, nearby idea (Tempe Town Lake walk, Hayden Library
  rooftop, the dining hall) and ask if they want to widen the dates.
- A site needs a login the student won't do: skip that source, don't ask twice.
