# Weekly Scheduling Workflow

Two ways to run this: a simple browser-based UI (recommended for
day-to-day use), or the command line directly (useful for automation or
if you're comfortable with it).

## Option A: Web UI (drag files in, click a button)

**One-time setup:**
```
pip install flask ortools numbers-parser
```

**Every time you want to run it:**
```
python app.py
```
Then open **http://127.0.0.1:5000** in your browser. Leave that terminal
window open while you use it (it's what's actually doing the work) --
you can minimize it. Press Ctrl+C in that window when you're done.

The page shows:
- A required upload for this week's availability export
- Collapsible "advanced" sections for the other files (staff export,
  timecard, targets, pools, presence rules, preferred assignments) --
  only open those when something actually changed
- A live status panel showing what's currently cached and ready to reuse
- A "Build this week's schedule" button that runs everything and gives
  you a download link plus a summary (shifts filled, total cost, any
  gaps) right there on the page

This is the same underlying `run_week.py` engine, just with a proper
interface on top instead of typing command-line flags.

**Note:** this runs locally on your own computer -- nothing gets
uploaded anywhere else. If multiple people need to use it, each person
runs their own copy (or you run it on one shared computer and everyone
uses that machine).

## Option B: Command line

If you'd rather script this or run it unattended, everything below
still works exactly the same way via `run_week.py` directly.


## The one thing that's basically guaranteed to change every week

Availability. So that's the one input you'll almost always have on hand.

## Your normal week (the fast path)

1. Pull this week's Availability Report CSV from HotSchedules.
2. Run:
   ```
   python run_week.py --new-availability ThisWeeksAvailability.csv --output schedule_week32.csv
   ```
3. Open `schedule_week32.csv`.

That's it. It automatically reuses last week's roster, pay rates, shift
requirements, leadership pools, and preferred assignments from the
`state/` folder -- you don't re-supply any of that unless it changed.

## When something else changed

**Someone was hired, fired, or their job titles changed** -- also pass
the staff export:
```
python run_week.py --new-availability ThisWeek.csv \
                    --new-staff-export staffExport.numbers \
                    --output schedule_week32.csv
```
(You don't need to do this for a plain new hire who hasn't been added
to HotSchedules' role system yet either -- if a new name shows up in
the availability file that isn't in the roster, the script adds them
automatically with blank roles and tells you so in the output. They
just won't get scheduled until roles are filled in, either by you
editing `state/roster.csv` directly or by re-running with a fresh
staff export.)

**Pay rates changed, or you want to recalibrate shift timing against a
newer week of actual timecard data** -- also pass the timecard:
```
python run_week.py --new-availability ThisWeek.csv \
                    --new-timecard LastWeekTimecard.csv \
                    --output schedule_week32.csv
```

**Department hour budgets changed** -- also pass new targets (usually
paired with a new timecard, since targets feed into shift requirement
calibration):
```
python run_week.py --new-availability ThisWeek.csv \
                    --new-timecard LastWeekTimecard.csv \
                    --new-targets NewDeptTargets.csv \
                    --output schedule_week32.csv
```

**Leadership pool, presence rules, or pinned assignments changed** --
no flag needed. Just open and edit these files directly in `state/`:
- `state/pools.csv`
- `state/presence_requirements.csv`
- `state/preferred_assignments.csv`

They're reused automatically every run, whatever's currently in them.
(You can also pass `--pools`, `--presence-requirements`, or
`--preferred-assignments` with a new file path to overwrite them in one
step instead of hand-editing.)

## First-time setup

The very first run needs everything, since there's no cache yet:
```
python run_week.py \
    --new-availability AvailabilityReport.csv \
    --new-staff-export staffExport.numbers \
    --new-timecard TimecardReport.csv \
    --new-targets DeptHoursTarget.csv \
    --output schedule_week1.csv
```
After that, `state/` has everything and future weeks are the one-line
fast path.

## What's in `state/` and when it gets rebuilt

| File | Rebuilt when... |
|---|---|
| `availability.csv` | Every run (this is the weekly input) |
| `roster.csv` | You pass `--new-staff-export`, or a new name shows up in availability |
| `hourly_rates.csv` | You pass `--new-timecard` |
| `shift_requirements.csv` | You pass `--new-timecard` (and needs `targets.csv` to exist) |
| `targets.csv` | You pass `--new-targets` |
| `employees.csv` | Every run (cheap merge of roster + rates) |
| `pools.csv` | Only if you edit it directly or pass `--pools` |
| `presence_requirements.csv` | Only if you edit it directly or pass `--presence-requirements` |
| `preferred_assignments.csv` | Only if you edit it directly or pass `--preferred-assignments` |

## A few things worth knowing

- **Solve time**: budget ~2 minutes with `--time-limit 120` (the
  default) for a team this size. If you're in a hurry and willing to
  accept a slightly less cost-optimal (but still fully valid) schedule,
  lower `--time-limit`; the solver will use whatever time it's given
  and return its best answer so far.
- **Missing pay rates**: if someone genuinely has no rate on file
  anywhere (new hire, wasn't in the last timecard period), their rate
  gets estimated from the average for their primary role rather than
  breaking the run. The console output tells you how many people got
  an estimated rate each run -- worth a periodic sanity check.
- **Employee IDs stay stable** week to week (matched by name), so if
  you've referenced someone's `employee_id` in `pools.csv` or
  `preferred_assignments.csv`, it'll keep working in future weeks
  without needing to update it.
- **Sunday and Training hours are intentionally excluded** from
  required shifts, per how `shift_requirements.csv` was originally
  calibrated (store closed Sunday; Training isn't counted as required
  coverage). If either of those change, let me know and I can adjust
  the calibration logic in `build_shift_requirements`.

## Pools, presence requirements, and preferred assignments -- simplified

**Use names, not employee IDs.** Every optional file now accepts a
person's name directly (case-insensitive) -- no need to look anything
up first. If you misspell a name, you'll get a clear warning with a
suggestion ("did you mean...") rather than a silent failure.

**Preferred assignment times are now optional.** You don't need to know
exact shift block boundaries anymore:
- Leave `start_time`/`end_time` blank to mean "any shift of this role on
  this day for this person" -- the solver figures out which actual
  shift block that maps to.
- If you do give a rough time window (e.g. "8am-12pm"), it just needs
  to fall within some real shift -- it doesn't have to match a shift's
  exact start/end time.

Example `preferred_assignments.csv`:
```
day,role,name,weight,start_time,end_time
Mon,Grill,Gage Peoples,1000,,
Wed,Server,Aijah Smith,1000,08:00,12:00
```
The first row means "Gage on Grill Monday, whichever shift block that
ends up being." The second means "Aijah on Server Wednesday, sometime
covering 8am-12pm."

Example `pools.csv`:
```
pool_name,name
Leadership_Pool,Adam Dunn
Leadership_Pool,Andrew Durrance
```

`presence_requirements.csv` is unchanged (it already worked this
flexible way) -- it checks whether whatever shift a pool member ends up
on happens to cover the required window, so you never had to know exact
shift boundaries there either.

## Requirements

```
pip install ortools numbers-parser
```
