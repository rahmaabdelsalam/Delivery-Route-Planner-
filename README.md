# Delivery Route Planner

The Delivery Route Planner is a command-line program that takes a list of
delivery requests and organizes them into vehicle trips. It enforces a
maximum vehicle capacity of 10 kg per trip, groups deliveries within the
same area together, and processes higher-priority (lower-number) deliveries
first. On top of that required plan, it also analyzes the result and
recommends merging trips between geographically neighboring areas whenever
that would still respect capacity and priority, without ever changing the
required plan itself.

## Setup

1. Make sure Python 3.10+ is available:
   ```bash
   python3 --version
   ```
2. Clone or unzip this repository and `cd` into it.

## How to Run

```bash
python3 src/route_planner.py samples/sample_deliveries_1.csv
```

Or, for the same result as structured JSON instead of plain text:

```bash
python3 src/route_planner.py samples/sample_deliveries_1.csv --json
```

To try any of the other sample files, just swap the file name in the
command above (or point it at your own CSV, as long as it follows the
format described next).

## Input Format — Why CSV

CSV was chosen as the input format because this is a list of flat, uniform
records — every delivery has exactly the same four fields — and CSV is the
simplest way to represent that. It's also easy to open and check by eye or
in Excel/Sheets, which matters for a delivery-operations tool that a
non-developer might need to prepare or review by hand.

The file must have a header row with these four columns:

| Column       | Type  | Rules                                             |
|--------------|-------|----------------------------------------------------|
| `id`         | int   | must be unique across the file                    |
| `area`       | text  | must be one of the supported areas (see below)    |
| `priority`   | int   | `>= 1`; the lower the number, the more urgent      |
| `weight_kg`  | float | `> 0` and `<= 10` (the vehicle's per-trip capacity) |

Supported areas (not case-sensitive): `Heliopolis`, `Nasr City`,
`New Cairo`, `Maadi`, `Zamalek`.

Any row that breaks one of these rules is skipped rather than crashing the
program — it shows up in a `WARNINGS` section in the output instead, with
the line number and the exact reason it was rejected.

## Sample Input Files

Five sample files are included in `samples/`:

- `sample_deliveries_1.csv` mirrors the example data from the problem
  statement.
- `sample_deliveries_2.csv` is a larger, fully valid dataset showing the
  general approach across all five areas.
- `sample_deliveries_3.csv`, `sample_deliveries_4.csv`, and
  `sample_deliveries_5.csv` each mix a few different validation issues at
  once (things like a duplicate ID, an overweight package, an unsupported
  area, or a capacity-boundary case) alongside otherwise valid deliveries —
  so you can see each issue get skipped with a clear reason while the rest
  of the file still gets planned normally, recommendations included.

## Approach

The program works in two stages, printed one after the other so it's clear
which part is required and which part is additional:

**Step 1 — the baseline plan.** This is the required part. Deliveries are
sorted by priority first, then by area, then by ID (so the order is always
predictable, even when priorities tie). They're then packed into trips: a
delivery only joins the current trip if it's going to the *same area* and
the trip still has room under 10 kg — otherwise a new trip starts. That one
rule is enough to satisfy every required behavior: trips never exceed
capacity, deliveries to the same area end up together, more urgent
deliveries are handled first, and every valid delivery ends up in exactly
one trip.

**Step 2 — the recommendation (the extension).** Explained in its own
section below.

## Answers to the Reasoning Questions

**1. Explain your solution approach in your own words.**
Every row is read and validated on the way in, so bad data gets filtered
out early with a clear reason instead of breaking the whole run. What's
left is sorted by priority, area, and ID, and packed into trips greedily,
closing a trip the moment the next delivery either belongs to a different
area or would push it over 10 kg. That produces the required baseline
plan. A second, separate pass then looks for pairs or small groups of
trips from different but nearby areas that could be combined into one
vehicle trip without breaking capacity or priority order, and prints those
as suggestions rather than applying them.

**2. What was the most difficult part of the assignment?**
Resisting the urge to make the grouping smarter than it needed to be. The
first instinct was to look for the mathematically optimal packing across
all areas at once, but the actual requirement is simpler: same area, same
trip, under capacity, priority first — nothing about cross-area
optimization. The harder part became keeping that required rule simple and
provably correct, and pushing anything cleverer (the cross-area merging)
into a clearly separate, optional step that never touches the required
output. Keeping those two things cleanly separated in the code — not just
in the printed output — took more care than the packing logic itself.

**3. Are there situations where your algorithm may not produce the best
possible grouping?**
Yes. The baseline packer is greedy and doesn't backtrack: it processes
deliveries in priority/area/ID order and never revisits a trip once it
moves past it. So it's possible to end up with two trips that are both
partially full for the same area, when a different ordering could have
combined them into one trip. This wasn't "fixed" with a full bin-packing
algorithm on purpose — the priority requirement (handle lower numbers
first) would conflict with reordering purely to save capacity, and
respecting priority strictly was treated as more important than saving a
trip here and there. The same applies to the recommendation step: it looks
for the largest connected group of trips starting from each unassigned
trip, but it doesn't try every possible way to partition the whole set, so
with a lot of areas and trips it might occasionally miss a merge that a
full search would have found.

**4. If the input contained 1,000,000 delivery requests, what part of your
solution might become slow or memory-intensive?**
Two things stand out. First, every delivery is loaded into memory as a
list before any processing happens, so memory use grows in a straight line
with the size of the file. Second, and more seriously, the recommendation
search in Step 2 is recursive and explores combinations of trips within a
connected group of areas — it isn't capped at a fixed group size, so if a
large number of small trips end up in the same connected area cluster,
that search could get slow. The baseline packing itself is just a sort
plus a single pass, so that part stays fast even at a million rows — it's
the optional Step 2 search that would need attention first.

**5. What would you improve if you had another day to work on the
solution?**
A limit on how large a group the Step 2 search is allowed to explore, so
it can't blow up on a pathological input, and streaming the CSV instead of
reading it fully into memory. The greedy baseline packer could also be
swapped for something like first-fit-decreasing within each area (still
respecting priority order first) to reduce the wasted capacity mentioned
in question 3.

## Extension: Neighboring-Area Merge Recommendation

The one addition beyond the required behavior is the **Step 2
recommendation**. Here's what it does and why it's there:

**What it does.** After the required same-area, priority-ordered plan is
built, a separate check looks at whether any of those trips go to
*different but nearby* areas — a small adjacency map is used (Heliopolis ↔
Nasr City ↔ New Cairo ↔ Maadi, with Zamalek standing alone since it isn't
close to the others) — and if two or more trips are connected in that map
and their combined weight still fits in one 10 kg vehicle load, it
suggests combining them into a single trip. Priority order is respected
across the merge too, so a low-priority trip is never recommended ahead of
a higher-priority one it isn't actually connected to.

**How it helps.** In real delivery operations, sending a separate vehicle
for a half-full trip to Maadi and another half-full trip to neighboring New
Cairo is wasteful if one van could realistically cover both on the same
run. This turns that observation into a concrete, checkable suggestion — a
dispatcher looking at the output can see exactly which trips are proposed
for merging, what the combined weight would be, and how many total trips
would be saved, instead of spotting that opportunity manually.

**Why it's relevant to this specific problem.** The core rule set (area
grouping, priority, capacity) practically invites this next question —
"could this use fewer vehicles?" — since it's the natural next lever after
grouping by area. Geography is the one constraint the base rules don't
consider at all, so this extension fills exactly that gap using only the
area names already present in the data.

**Why it stays a recommendation instead of changing the plan.** This was a
deliberate choice, and it's the part that reflects the most judgment
rather than the most code. The required rules exist for safety and
correctness — capacity limits and urgency — so a "smart" optimization
should never silently override those guarantees. Step 2 never rewrites the
baseline plan; it only prints suggestions and a separate preview of what
accepting them would look like. That keeps the required behavior fully
correct and easy to trust on its own, while the extension remains a bonus
a dispatcher can act on or ignore. This was chosen over a "bigger" feature
(like actual route or distance optimization) on purpose, since there's no
real distance or road data to work with here — a small, fully understood
feature was preferred over a more ambitious one built on assumptions that
couldn't be backed up.

## Edge Cases Handled

- **No deliveries at all** — the baseline plan reports zero trips instead
  of erroring.
- **A package heavier than the 10 kg capacity** — that row is rejected
  with a clear warning instead of being silently dropped or allowed to
  break capacity somewhere else.
- **Multiple deliveries with the same priority** — ties are broken
  consistently by area, then by ID, so the output never changes between
  runs on the same input.
- **Adding the next package would exceed capacity** — a new trip starts
  for that delivery rather than overfilling the current one.
- **Duplicate IDs, unsupported/empty areas, non-numeric or invalid
  fields** — each is rejected individually with its own warning and line
  number, and the rest of the file still gets processed normally.

## Project Structure

```
.
├── README.md
├── src/
│   └── route_planner.py        # main program
└── samples/
    ├── sample_deliveries_1.csv # mirrors the problem statement's example
    ├── sample_deliveries_2.csv # larger, fully valid dataset
    ├── sample_deliveries_3.csv # mixed validation issues + valid data
    ├── sample_deliveries_4.csv # mixed validation issues + valid data
    └── sample_deliveries_5.csv # mixed validation issues + valid data
```