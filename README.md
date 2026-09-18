# Delivery Route Planner

A small command-line program that organizes a list of delivery requests into
vehicle trips, following capacity, priority, and area-grouping rules.

## How to Run

Requires Python 3.10+ (no external dependencies).

```bash
python3 route_planner.py sample_deliveries.csv
```

Optional JSON output:

```bash
python3 route_planner.py sample_deliveries.csv --json
```

### Input format

CSV with a header row and these required columns:

| Column       | Type  | Notes                                   |
|--------------|-------|------------------------------------------|
| `id`         | int   | Must be unique                          |
| `area`       | text  | Must be one of the supported areas below |
| `priority`   | int   | `>= 1`; lower number = more urgent      |
| `weight_kg`  | float | `> 0` and `<= 10` (vehicle capacity)    |

Supported areas (case-insensitive): `Heliopolis`, `Nasr City`, `New Cairo`,
`Maadi`, `Zamalek`.

A sample file, `sample_deliveries.csv`, is included in this repository.

Any row that fails validation (duplicate ID, unsupported area, non-positive
weight, weight over capacity, etc.) is **skipped** and reported in the
`WARNINGS` section of the output — it does not stop the program from
processing the rest of the file.

## Solution Approach

The program works in two clearly separated stages, printed one after the
other:

**Step 1 — Baseline plan (required rules).**
This is the mandatory part of the assignment. Deliveries are sorted by
priority first, then by area, then by ID. They are then packed into trips
greedily: a delivery joins the current trip only if it belongs to the *same
area* and still fits under the 10 kg capacity; otherwise a new trip is
started. This guarantees:
- every trip stays within a single area,
- every trip stays within the 10 kg capacity,
- more urgent (lower-priority-number) deliveries are handled first,
- every valid delivery appears in exactly one trip.

**Step 2 — Recommendation (optional extension, not part of the required
rules).** After the baseline plan is printed in full, the program looks for
opportunities to *merge* baseline trips from different but **geographically
neighboring** areas (e.g. Heliopolis ↔ Nasr City ↔ New Cairo ↔ Maadi) into a
single vehicle trip, as long as:
- the areas are directly connected in a configured adjacency map,
- the combined weight of the merged trips stays within 10 kg,
- priority order across the merged trips is respected (no later-priority
  group is merged ahead of an earlier one it isn't connected to).

This is printed as an explicit, clearly labeled **recommendation** — the
baseline plan is never changed automatically. A full "recommended
alternative plan" is also shown so it's easy to see exactly how many trips
would be saved if the merge suggestions were accepted.

## README / Reasoning Questions

**1. Explain your solution approach in your own words.**
See "Solution Approach" above: read and validate the CSV, sort deliveries by
priority/area/ID, greedily pack same-area deliveries into capacity-limited
trips for the required baseline plan, then run a separate, optional search
over the baseline trips to recommend merges across neighboring areas
without violating capacity or priority order.

**2. What was the most difficult part of the assignment?**
Keeping the "required" and "optional" parts of the logic cleanly separated —
both in the code and in the printed output — so the baseline plan always
satisfies the assignment's rules on its own, and the neighboring-area merge
logic stays purely advisory (search-based, exploring combinations of
connected trips) without ever silently changing the required plan.

**3. Are there situations where your algorithm may not produce the best
possible grouping?**
Yes. The baseline packer is greedy: it fills each area's trips in
priority/ID order and never backtracks, so a slightly different ordering
could sometimes leave less "wasted" capacity (e.g. two 6 kg deliveries to
the same area end up as two half-empty trips instead of being combined with
a smaller delivery that arrives later in the sort order). Likewise, the
merge-recommendation step picks the *largest* connected group it can find
starting from each unused trip, but it doesn't try every possible
combination of groupings across the whole dataset — with many areas and
trips, a different partition could occasionally save one more trip.

**4. If the input contained 1,000,000 delivery requests, what part of your
solution might become slow or memory-intensive?**
- The whole file is read into memory as a list of `Delivery` objects before
  planning starts — memory grows linearly with the number of deliveries.
- The recommendation search (`_find_best_group`) explores combinations of
  baseline trips recursively; with a very large number of small trips in
  the same connected component, this could grow expensive, since it isn't
  bounded to a fixed group size.
- Sorting is O(n log n), which stays fine, but building the baseline trips
  itself is O(n) and would not be the bottleneck compared to the
  recommendation search.

**5. What would you improve if you had another day to work on the
solution?**
- Stream the CSV instead of loading it fully into memory, and cap or
  memoize the recommendation search so it scales predictably on large,
  highly-connected inputs.
- Add a proper bin-packing/optimization pass (e.g. first-fit-decreasing by
  weight within each area) instead of pure greedy packing, to reduce wasted
  capacity in the baseline plan.
- Add unit tests covering the edge cases explicitly (empty input,
  over-capacity single package, duplicate IDs, unsupported area, ties in
  priority).
- Make the area-adjacency map configurable (e.g. via a JSON/YAML file)
  instead of hard-coded, so new areas and links can be added without
  touching the code.

## Extension: Neighboring-Area Merge Recommendation

The one feature added beyond the core requirements is the **Step 2
recommendation** described above: after the required same-area/priority
plan is built, the program separately analyzes it and suggests where
merging trips from adjacent areas would save vehicle trips — without ever
changing the required plan itself. This was chosen because it directly
extends the delivery domain (fewer vehicle trips = lower cost) while
staying safe: it's clearly labeled as optional, is capacity- and
priority-aware, and the required baseline output is unaffected whether or
not the recommendation is accepted.

## Edge Cases Handled

- **No deliveries** → baseline plan reports zero trips instead of erroring.
- **Package heavier than 10 kg capacity** → row is rejected with a warning,
  not silently dropped or allowed to break capacity elsewhere.
- **Same priority** → ties are broken by area, then by ID, so ordering is
  deterministic.
- **Adding the next package would exceed capacity** → a new trip is started
  for that delivery instead.
- **Unsupported / empty area, duplicate ID, non-numeric fields** → row is
  skipped and listed under `WARNINGS`, and processing continues for the
  rest of the file.