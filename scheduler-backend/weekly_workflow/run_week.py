#!/usr/bin/env python3
"""
run_week.py
=============
ONE COMMAND TO RUN THE WEEKLY SCHEDULE.

This ties together everything built so far (HotSchedules availability
conversion, staff roster/role parsing, timecard-based pay rate + shift
requirement calibration, and the CP-SAT solver with pools/presence/
preferred-assignment support) into a single weekly workflow.

THE KEY IDEA: not everything changes every week. Availability changes
every week -- that's the one file you'll basically always have to hand
this script. Your roster (who works here, what roles they're qualified
for), pay rates, department hour targets, leadership pools, and
preferred-assignment rules change rarely, if ever. So this script
remembers all of that in a `state/` folder and only re-processes the
pieces you tell it have changed.

------------------------------------------------------------------------
TYPICAL WEEK (the fast path -- this is what you'll do almost every time)
------------------------------------------------------------------------
    python run_week.py --new-availability ThisWeeksAvailability.csv \
                        --output schedule_week32.csv

That's it. It reuses last week's roster, pay rates, shift requirements,
pools, and preferences automatically, and just re-solves against this
week's availability.

------------------------------------------------------------------------
WHEN SOMETHING ELSE CHANGED
------------------------------------------------------------------------
New hire / someone's roles changed -> also pass --new-staff-export (the
.numbers staff export):
    python run_week.py --new-availability ThisWeek.csv \
                        --new-staff-export staffExport.numbers \
                        --output schedule_week32.csv

Pay rates changed / you want to recalibrate shift timing against a fresh
timecard week -> also pass --new-timecard (and optionally --new-targets
if the department hour budgets changed too):
    python run_week.py --new-availability ThisWeek.csv \
                        --new-timecard LastWeekTimecard.csv \
                        --output schedule_week32.csv

Leadership pool / presence rules / pinned assignments changed -> just
edit state/pools.csv, state/presence_requirements.csv, or
state/preferred_assignments.csv directly (they're plain CSVs), no flags
needed -- the script always reads whatever's currently in state/.

------------------------------------------------------------------------
FIRST-TIME SETUP
------------------------------------------------------------------------
The very first run needs everything:
    python run_week.py \
        --new-availability AvailabilityReport.csv \
        --new-staff-export staffExport.numbers \
        --new-timecard TimecardReport.csv \
        --new-targets DeptHoursTarget.csv \
        --output schedule_week1.csv

After that, state/ has everything cached and subsequent weeks are the
one-line fast path above.

------------------------------------------------------------------------
STATE FOLDER CONTENTS (--state-dir, default ./state)
------------------------------------------------------------------------
    availability.csv           this week's availability (always rebuilt)
    roster.csv                 name/employee_id/roles (rebuilt only when --new-staff-export given)
    hourly_rates.csv           pay rates (rebuilt only when --new-timecard given)
    targets.csv                department daily hour targets (rebuilt only when --new-targets given)
    shift_requirements.csv     shift blocks (rebuilt only when --new-timecard or --new-targets given)
    employees.csv              merged roster+rates, solver-ready (rebuilt whenever roster or rates change)
    pools.csv                  (optional, hand-edited, reused as-is)
    presence_requirements.csv  (optional, hand-edited, reused as-is)
    preferred_assignments.csv  (optional, hand-edited, reused as-is)

Requires: pip install ortools numbers-parser
"""

import argparse
import csv
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

from ortools.sat.python import cp_model

DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

ROLE_TO_DEPT = {
    "BOH - General": "Back of House", "Grill": "Back of House", "Dishes": "Back of House",
    "Prep": "Back of House", "Biscuits": "Back of House", "BOH - Open": "Back of House",
    "Boards": "Back of House", "Machines": "Back of House", "Raw Chicken": "Back of House",
    "Breader": "Back of House", "Fries": "Back of House", "Chicken": "Back of House",
    "Truck": "Back of House",
    "Self Serve - General": "Self Service", "Cashier": "Self Service",
    "Server": "Full Service", "Dining Room Host - Full Serve": "Full Service",
    "Dining Room Assistant": "Full Service", "Full Serve - General": "Full Service",
    "Director": "Leadership", "Area Supervisor": "Leadership", "GeneralMgr - Exempt": "Leadership",
    "Administrative": "Other", "Maintenance": "Other", "Scheduler": "Other",
    "Off-Site Sales": "Other", "ADP General": "Other", "Drive-Thru": "Other",
    "In Training": "Training", "Trainer": "Training",
}


def log(msg):
    print(msg, flush=True)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


# ========================================================================
# STEP 1: Availability conversion (HotSchedules export -> long format)
# ========================================================================

def slugify_id(name, seen):
    base = re.sub(r"[^A-Za-z]+", "_", name.strip()).strip("_").upper()
    eid = base
    n = 2
    while eid in seen:
        eid = f"{base}_{n}"
        n += 1
    seen.add(eid)
    return eid


def parse_12hr(t):
    dt = datetime.strptime(t.strip(), "%I:%M %p")
    return dt.strftime("%H:%M")


def parse_availability_cell(cell):
    cell = cell.strip()
    if not cell or cell.lower().startswith("unavailable"):
        return []
    if cell.lower().startswith("available all day"):
        return [("00:00", "23:59")]
    if cell.lower().startswith("partially available"):
        body = cell[len("Partially Available"):].strip()
        windows = []
        for part in body.split(","):
            part = part.strip()
            m = re.match(r"(\d{1,2}:\d{2}\s*[APap][Mm])\s*-\s*(\d{1,2}:\d{2}\s*[APap][Mm])", part)
            if not m:
                continue
            start, end = parse_12hr(m.group(1)), parse_12hr(m.group(2))
            if end == "00:00":
                end = "23:59"
            windows.append((start, end))
        return windows
    return []


def convert_availability(input_path, state_dir):
    """Returns (list of employee names seen this week) and writes state/availability.csv"""
    with open(input_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        day_cols = [h.strip()[:3] for h in header[1:]]

        avail_rows = []
        names_seen = []
        seen_ids = set()
        name_to_id = {}

        # if a roster already exists, reuse its employee_id assignments so IDs stay stable week to week
        roster_path = os.path.join(state_dir, "roster.csv")
        if os.path.exists(roster_path):
            with open(roster_path, newline="", encoding="utf-8-sig") as rf:
                for row in csv.DictReader(rf):
                    name_to_id[row["name"].strip()] = row["employee_id"]
                    seen_ids.add(row["employee_id"])

        for row in reader:
            if not row or not row[0].strip():
                continue
            name = row[0].strip()
            names_seen.append(name)
            eid = name_to_id.get(name) or slugify_id(name, seen_ids)
            name_to_id[name] = eid
            for day, cell in zip(day_cols, row[1:]):
                for (start, end) in parse_availability_cell(cell):
                    avail_rows.append({"employee_id": eid, "day": day, "start_time": start, "end_time": end})

    out_path = os.path.join(state_dir, "availability.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["employee_id", "day", "start_time", "end_time"])
        w.writeheader()
        w.writerows(avail_rows)

    log(f"  Availability: {len(names_seen)} people, {len(avail_rows)} windows -> {out_path}")
    return names_seen, name_to_id


# ========================================================================
# STEP 2: Staff roster / roles (from .numbers staff export)
# ========================================================================

def reconstruct_numbers_xml(numbers_path):
    from numbers_parser import Document
    doc = Document(numbers_path)
    table = doc.sheets[0].tables[0]
    rows = table.rows(values_only=True)
    lines = []
    for row in rows:
        cells = [c for c in row if c is not None]
        lines.append(",".join(cells))
    xml_text = "\n".join(lines)
    start = xml_text.find("<?xml")
    return xml_text[start:] if start > 0 else xml_text


def parse_jobs_cell(jobs_text):
    if not jobs_text:
        return []
    m = re.match(r"^\d+\s+Jobs?\s*\((.*)\)$", jobs_text.strip())
    body = m.group(1) if m else jobs_text.strip()
    roles = [re.sub(r"\s+", " ", r).strip() for r in body.split(",")]
    return [r for r in roles if r]


def convert_staff_export(numbers_path, state_dir, name_to_id):
    NS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
    xml_text = reconstruct_numbers_xml(numbers_path)
    root = ET.fromstring(xml_text)
    worksheet = root.find("ss:Worksheet", NS)
    table = worksheet.find("ss:Table", NS)
    rows = table.findall("ss:Row", NS)

    parsed_rows = []
    for r in rows:
        cells = r.findall("ss:Cell", NS)
        vals = []
        for c in cells:
            data = c.find("ss:Data", NS)
            vals.append(data.text if data is not None and data.text else "")
        parsed_rows.append(vals)

    header_idx = next((i for i, row in enumerate(parsed_rows) if row and row[0].strip() == "Name"), None)
    if header_idx is None:
        raise ValueError("Could not find header row starting with 'Name' in staff export.")
    header = parsed_rows[header_idx]
    col_count = len(header)

    out_rows = []
    for row in parsed_rows[header_idx + 1:]:
        if not row or not row[0].strip():
            continue
        name = row[0].strip()
        if re.match(r"^[A-Za-z]{3}\s+\d{1,2},\d{4}", name):
            continue
        row = (row + [""] * col_count)[:col_count]
        record = dict(zip(header, row))
        jobs = parse_jobs_cell(record.get("Jobs", ""))
        eid = name_to_id.get(name)
        if eid is None:
            # person in staff export but not (yet) in availability export -- assign an id anyway
            eid = re.sub(r"[^A-Za-z]+", "_", name.strip()).strip("_").upper()
            name_to_id[name] = eid
        out_rows.append({
            "employee_id": eid, "name": name,
            "detailed_roles": ";".join(jobs),
            "permission_set": record.get("Permission Set", "").strip(),
            "min_hours": "0", "max_hours": "40",
        })

    out_path = os.path.join(state_dir, "roster.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["employee_id", "name", "detailed_roles", "permission_set", "min_hours", "max_hours"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    log(f"  Roster: {len(out_rows)} people with role data -> {out_path}")
    return out_path


def sync_roster_with_this_weeks_names(state_dir, names_seen, name_to_id):
    """Make sure everyone appearing in this week's availability has a roster
    row (even if blank roles, flagged for manual fill-in), without discarding
    people already in the roster who simply aren't in this week's availability."""
    roster_path = os.path.join(state_dir, "roster.csv")
    existing = {}
    if os.path.exists(roster_path):
        with open(roster_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                existing[row["name"]] = row

    new_people = []
    for name in names_seen:
        if name not in existing:
            eid = name_to_id[name]
            existing[name] = {
                "employee_id": eid, "name": name, "detailed_roles": "",
                "permission_set": "", "min_hours": "0", "max_hours": "40",
            }
            new_people.append(name)

    if new_people:
        log(f"  NOTE: {len(new_people)} new name(s) in this week's availability with no role data yet "
            f"(added to roster.csv with blank roles -- fill in manually, or provide --new-staff-export): "
            f"{new_people}")
        with open(roster_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["employee_id", "name", "detailed_roles", "permission_set", "min_hours", "max_hours"]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(existing.values())


# ========================================================================
# STEP 3: Timecard parsing -> hourly rates + shift_requirements
# ========================================================================

def parse_money(s):
    if not s or s.strip() in ("-", ""):
        return 0.0
    return float(s.replace("$", "").replace(",", "").strip())


def parse_hours(s):
    if not s or s.strip() in ("-", ""):
        return 0.0
    return float(s.replace(",", "").strip())


def parse_clock_time(t):
    dt = datetime.strptime(t.strip(), "%I:%M %p")
    return dt.hour * 60 + dt.minute


def parse_date_to_day(date_str):
    dt = datetime.strptime(date_str.strip(), "%m/%d/%y")
    return dt.strftime("%a")


def round_to_30(minutes):
    return round(minutes / 30) * 30


def build_job_title_fixer(roster_path):
    canonical = set()
    with open(roster_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            for r in row["detailed_roles"].split(";"):
                r = r.strip()
                if r:
                    canonical.add(r)

    def fix(name):
        name = name.strip()
        if name.endswith("[Other Store]"):
            name = name.replace("[Other Store]", "").strip()
        if name in canonical:
            return name
        matches = [c for c in canonical if c.startswith(name)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return sorted(matches, key=len)[0]
        return name

    return fix


def load_timecard_shift_rows(timecard_path, fix_job_title):
    with open(timecard_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)
        rows = list(reader)

    shift_rows = []
    current_name = None
    for row in rows:
        if not row:
            continue
        if row[0] == "" and len(row) > 1 and row[1].strip() == "Job":
            break
        name_cell = row[0].strip()
        job = row[1].strip() if len(row) > 1 else ""
        date_cell = row[3].strip() if len(row) > 3 else ""
        if name_cell:
            current_name = name_cell
        if not date_cell:
            continue
        in_time, out_time = row[4].strip(), row[5].strip()
        reg_hours = parse_hours(row[6]) if len(row) > 6 else 0.0
        reg_usd = parse_money(row[7]) if len(row) > 7 else 0.0
        if reg_hours <= 0:
            continue
        try:
            day = parse_date_to_day(date_cell)
            in_min = parse_clock_time(in_time)
            out_min = parse_clock_time(out_time)
        except ValueError:
            continue
        job_fixed = fix_job_title(job)
        shift_rows.append({
            "name": current_name, "job": job_fixed, "day": day,
            "in_min": in_min, "out_min": out_min, "hours": reg_hours, "usd": reg_usd,
        })
    return shift_rows


def clean_shared_name(name):
    return re.sub(r"\s*\[Shared\]\s*$", "", name.strip())


def build_hourly_rates(shift_rows, state_dir):
    rates_by_emp = defaultdict(list)
    for s in shift_rows:
        rate = s["usd"] / s["hours"]
        rates_by_emp[clean_shared_name(s["name"])].append(round(rate, 4))

    out_rows = []
    for name, rates in rates_by_emp.items():
        avg_rate = sum(rates) / len(rates)
        out_rows.append({"name": name, "hourly_rate": round(avg_rate, 2)})

    out_path = os.path.join(state_dir, "hourly_rates.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "hourly_rate"])
        w.writeheader()
        w.writerows(sorted(out_rows, key=lambda r: r["name"]))

    log(f"  Hourly rates: {len(out_rows)} people -> {out_path}")
    return out_path


def build_shift_requirements(shift_rows, targets_path, roster_path, state_dir):
    dept_daily_target = {}
    with open(targets_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            dept_daily_target[row["Department"].strip()] = float(row["Daily Hours Required"])

    role_weekly_hours = defaultdict(float)
    for s in shift_rows:
        role_weekly_hours[s["job"]] += s["hours"]

    dept_weekly_hours_hist = defaultdict(float)
    for role, hrs in role_weekly_hours.items():
        dept = ROLE_TO_DEPT.get(role)
        if dept:
            dept_weekly_hours_hist[dept] += hrs

    role_weekly_target = {}
    for role, hrs in role_weekly_hours.items():
        dept = ROLE_TO_DEPT.get(role)
        if not dept or dept == "Training" or dept_daily_target.get(dept, 0) == 0:
            role_weekly_target[role] = 0.0
            continue
        dept_hist = dept_weekly_hours_hist.get(dept, 0.0)
        role_weekly_target[role] = 0.0 if dept_hist <= 0 else dept_daily_target[dept] * 6 * (hrs / dept_hist)

    day_role_windows = defaultdict(lambda: defaultdict(int))
    for s in shift_rows:
        if s["day"] == "Sun":
            continue
        start_r, end_r = round_to_30(s["in_min"]), round_to_30(s["out_min"])
        if end_r <= start_r:
            continue
        day_role_windows[(s["day"], s["job"])][(start_r, end_r)] += 1

    day_role_hist_hours = defaultdict(float)
    for (day, role), windows in day_role_windows.items():
        for (start, end), count in windows.items():
            day_role_hist_hours[(day, role)] += count * (end - start) / 60.0

    role_weekly_hist_total = defaultdict(float)
    for (day, role), hrs in day_role_hist_hours.items():
        role_weekly_hist_total[role] += hrs

    def fmt(m):
        h, mm = divmod(m, 60)
        return f"{h:02d}:{mm:02d}"

    out_rows = []
    for (day, role), windows in sorted(day_role_windows.items(), key=lambda kv: (DAY_ORDER.index(kv[0][0]), kv[0][1])):
        weekly_target = role_weekly_target.get(role, 0.0)
        if weekly_target <= 0:
            continue
        hist_total = role_weekly_hist_total.get(role, 0.0)
        if hist_total <= 0:
            continue
        day_hist_hours = day_role_hist_hours.get((day, role), 0.0)
        day_share = day_hist_hours / hist_total
        day_target_hours = weekly_target * day_share
        if day_target_hours <= 0:
            continue
        scale = day_target_hours / day_hist_hours if day_hist_hours > 0 else 0
        for (start, end), orig_count in sorted(windows.items()):
            scaled_count = round(orig_count * scale)
            if scaled_count <= 0:
                continue
            out_rows.append({"day": day, "role": role, "start_time": fmt(start),
                              "end_time": fmt(end), "count_needed": scaled_count})

    out_path = os.path.join(state_dir, "shift_requirements.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["day", "role", "start_time", "end_time", "count_needed"])
        w.writeheader()
        w.writerows(out_rows)

    log(f"  Shift requirements: {len(out_rows)} shift blocks -> {out_path}")
    return out_path


# ========================================================================
# STEP 4: Build final employees.csv (roster + rates merged, gaps filled)
# ========================================================================

def build_employees_csv(state_dir):
    roster_path = os.path.join(state_dir, "roster.csv")
    rates_path = os.path.join(state_dir, "hourly_rates.csv")

    rates_by_name = {}
    if os.path.exists(rates_path):
        with open(rates_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                rates_by_name[row["name"]] = row["hourly_rate"]

    rows = []
    with open(roster_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows.append({
                "employee_id": row["employee_id"], "name": row["name"],
                "roles": row["detailed_roles"],
                "hourly_rate": rates_by_name.get(row["name"], ""),
                "min_hours": row.get("min_hours", "0"),
                "max_hours": row.get("max_hours", "40"),
            })

    # fill missing rates with role-average fallback
    known_rates = [float(r["hourly_rate"]) for r in rows if r["hourly_rate"]]
    overall_avg = sum(known_rates) / len(known_rates) if known_rates else 15.0
    role_rates = defaultdict(list)
    for r in rows:
        if r["hourly_rate"]:
            primary_role = r["roles"].split(";")[0] if r["roles"] else ""
            role_rates[primary_role].append(float(r["hourly_rate"]))
    role_avg = {r: sum(v) / len(v) for r, v in role_rates.items()}

    filled = 0
    for r in rows:
        if not r["hourly_rate"]:
            primary_role = r["roles"].split(";")[0] if r["roles"] else ""
            r["hourly_rate"] = round(role_avg.get(primary_role, overall_avg), 2)
            filled += 1

    out_path = os.path.join(state_dir, "employees.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["employee_id", "name", "roles", "hourly_rate", "min_hours", "max_hours"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    log(f"  Employees (final): {len(rows)} people, {filled} rate(s) estimated via role average -> {out_path}")
    return out_path


# ========================================================================
# STEP 5: Solver (v2 -- pools / presence / preferred assignments)
# ========================================================================

def parse_time(t):
    h, m = t.strip().split(":")
    return int(h) * 60 + int(m)


def fmt_time(minutes):
    h, m = divmod(minutes, 60)
    return f"{h:02d}:{m:02d}"


def normalize_day(d):
    d = d.strip()[:3].capitalize()
    if d not in DAY_ORDER:
        raise ValueError(f"Unrecognized day '{d}'.")
    return d


def load_employees_for_solver(path):
    employees = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            eid = row["employee_id"].strip()
            employees[eid] = {
                "employee_id": eid, "name": row["name"].strip(),
                "roles": set(r.strip() for r in row["roles"].split(";") if r.strip()),
                "hourly_rate": float(row["hourly_rate"]),
                "min_hours": float(row["min_hours"]), "max_hours": float(row["max_hours"]),
            }
    return employees


def load_availability_for_solver(path, employees):
    avail = defaultdict(lambda: defaultdict(list))
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            eid = row["employee_id"].strip()
            if eid not in employees:
                continue
            day = normalize_day(row["day"])
            avail[eid][day].append((parse_time(row["start_time"]), parse_time(row["end_time"])))
    return avail


def load_requirements_for_solver(path):
    shifts = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for i, row in enumerate(csv.DictReader(f)):
            day = normalize_day(row["day"])
            start, end = parse_time(row["start_time"]), parse_time(row["end_time"])
            shifts.append({
                "shift_id": f"S{i}", "day": day, "role": row["role"].strip(),
                "start": start, "end": end, "hours": (end - start) / 60.0,
                "count_needed": int(row["count_needed"]),
            })
    return shifts


def build_name_lookup(employees):
    """lowercased, trimmed name -> employee_id, for friendly name-based lookups."""
    lookup = {}
    for eid, emp in employees.items():
        lookup[emp["name"].strip().lower()] = eid
    return lookup


def resolve_person(identifier, employees, name_lookup, context=""):
    """Accepts either a real employee_id or a person's name (case-insensitive)
    and returns the employee_id, or None with a helpful warning if it can't
    find a match."""
    identifier = identifier.strip()
    if identifier in employees:
        return identifier
    eid = name_lookup.get(identifier.lower())
    if eid:
        return eid
    import difflib
    close = difflib.get_close_matches(identifier.lower(), name_lookup.keys(), n=3, cutoff=0.6)
    suggestion = f" Did you mean: {', '.join(c.title() for c in close)}?" if close else ""
    print(f"  WARNING: could not find '{identifier}'{(' (' + context + ')') if context else ''} "
          f"in the roster -- check spelling.{suggestion}")
    return None


def load_pools_for_solver(path, employees):
    """pools.csv: pool_name, name  (an 'employee_id' column also still works,
    for anyone who prefers it)."""
    pools = defaultdict(set)
    if not path or not os.path.exists(path):
        return pools
    name_lookup = build_name_lookup(employees)
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        id_col = "name" if "name" in reader.fieldnames else "employee_id"
        for row in reader:
            eid = resolve_person(row[id_col], employees, name_lookup, context=f"pool '{row['pool_name']}'")
            if eid:
                pools[row["pool_name"].strip()].add(eid)
    return pools


def load_presence_for_solver(path):
    reqs = []
    if not path or not os.path.exists(path):
        return reqs
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        has_w = "priority_weight" in reader.fieldnames
        for row in reader:
            weight = float(row["priority_weight"]) if has_w and row.get("priority_weight", "").strip() else 100_000
            reqs.append({
                "day": normalize_day(row["day"]), "start": parse_time(row["start_time"]),
                "end": parse_time(row["end_time"]), "pool_name": row["pool_name"].strip(),
                "min_count": int(row["min_count"]), "priority_weight": weight,
            })
    return reqs


def load_preferred_for_solver(path, employees):
    """preferred_assignments.csv: day, role, name, weight (optional),
    start_time (optional), end_time (optional).

    - name: a person's name (or employee_id, both work)
    - start_time/end_time: OPTIONAL. Leave blank to mean "any shift of this
      role on this day for this person" -- you don't need to know the exact
      shift block boundaries. If you do give a time window, it just needs to
      fall WITHIN some real shift (doesn't have to match exactly)."""
    prefs = []
    if not path or not os.path.exists(path):
        return prefs
    name_lookup = build_name_lookup(employees)
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        has_w = "weight" in reader.fieldnames
        id_col = "name" if "name" in reader.fieldnames else "employee_id"
        has_times = "start_time" in reader.fieldnames and "end_time" in reader.fieldnames
        for row in reader:
            weight = float(row["weight"]) if has_w and row.get("weight", "").strip() else 1000
            eid = resolve_person(row[id_col], employees, name_lookup,
                                  context=f"preferred assignment ({row.get('day', '?')} {row.get('role', '?')})")
            if not eid:
                continue
            start_str = row.get("start_time", "").strip() if has_times else ""
            end_str = row.get("end_time", "").strip() if has_times else ""
            prefs.append({
                "day": normalize_day(row["day"]), "role": row["role"].strip(),
                "start": parse_time(start_str) if start_str else None,
                "end": parse_time(end_str) if end_str else None,
                "employee_id": eid, "weight": weight,
            })
    return prefs


def shifts_overlap(s1, s2):
    return s1["day"] == s2["day"] and s1["start"] < s2["end"] and s2["start"] < s1["end"]


def windows_cover_shift(windows, start, end):
    return any(a <= start and b >= end for a, b in windows)


def solve(employees, availability, shifts, pools, presence_reqs, preferred, time_limit_sec):
    model = cp_model.CpModel()
    x, eligible_pairs = {}, defaultdict(list)

    for shift in shifts:
        sid = shift["shift_id"]
        for eid, emp in employees.items():
            if shift["role"] not in emp["roles"]:
                continue
            windows = availability.get(eid, {}).get(shift["day"], [])
            if not windows_cover_shift(windows, shift["start"], shift["end"]):
                continue
            var = model.NewBoolVar(f"x_{eid}_{sid}")
            x[(eid, sid)] = var
            eligible_pairs[sid].append(eid)

    shift_lookup = {s["shift_id"]: s for s in shifts}

    shortfall = {}
    for shift in shifts:
        sid = shift["shift_id"]
        assigned = sum(x[(eid, sid)] for eid in eligible_pairs[sid])
        shortfall[sid] = model.NewIntVar(0, shift["count_needed"], f"short_{sid}")
        model.Add(assigned + shortfall[sid] == shift["count_needed"])

    by_employee = defaultdict(list)
    for (eid, sid) in x:
        by_employee[eid].append(sid)

    for eid, sids in by_employee.items():
        for i in range(len(sids)):
            for j in range(i + 1, len(sids)):
                s1, s2 = shift_lookup[sids[i]], shift_lookup[sids[j]]
                if shifts_overlap(s1, s2):
                    model.Add(x[(eid, sids[i])] + x[(eid, sids[j])] <= 1)

    for eid, emp in employees.items():
        sids = by_employee.get(eid, [])
        if not sids:
            continue
        expr = sum(x[(eid, sid)] * round(shift_lookup[sid]["hours"] * 60) for sid in sids)
        model.Add(expr <= round(emp["max_hours"] * 60))

    presence_shortfall = {}
    for i, req in enumerate(presence_reqs):
        pool_members = pools.get(req["pool_name"], set())
        contributing = []
        for eid in pool_members:
            for sid in by_employee.get(eid, []):
                s = shift_lookup[sid]
                if s["day"] == req["day"] and s["start"] <= req["start"] and s["end"] >= req["end"]:
                    contributing.append(x[(eid, sid)])
        rid = f"presence_{i}"
        if not contributing:
            presence_shortfall[rid] = (req["min_count"], req["priority_weight"])
            continue
        covered = model.NewIntVar(0, len(contributing), f"cov_{rid}")
        model.Add(covered == sum(contributing))
        short = model.NewIntVar(0, req["min_count"], f"short_{rid}")
        model.Add(covered + short >= req["min_count"])
        presence_shortfall[rid] = (short, req["priority_weight"])

    pref_bonus_terms = []
    pref_candidates = []  # (pref, [candidate (eid,sid) keys])
    for pref in preferred:
        if pref["start"] is None:
            # no time given -> any shift of this role/day counts
            candidate_sids = [s["shift_id"] for s in shifts if s["day"] == pref["day"] and s["role"] == pref["role"]]
        else:
            # time given -> match any shift whose window fully covers the requested window
            candidate_sids = [s["shift_id"] for s in shifts if s["day"] == pref["day"] and s["role"] == pref["role"]
                               and s["start"] <= pref["start"] and s["end"] >= pref["end"]]
        candidate_keys = [(pref["employee_id"], sid) for sid in candidate_sids if (pref["employee_id"], sid) in x]
        if candidate_keys:
            for key in candidate_keys:
                pref_bonus_terms.append(x[key] * round(pref["weight"] * 100))
        else:
            name = employees[pref["employee_id"]]["name"]
            time_desc = f" {fmt_time(pref['start'])}-{fmt_time(pref['end'])}" if pref["start"] is not None else ""
            print(f"  WARNING: preferred assignment for {name} on {pref['day']} {pref['role']}{time_desc} "
                  f"could not be honored: no matching shift found that they're eligible for "
                  f"(check role spelling against shift_requirements.csv, and their availability).")
        pref_candidates.append((pref, candidate_keys))

    cost_terms = [x[(eid, sid)] * round(employees[eid]["hourly_rate"] * shift_lookup[sid]["hours"] * 100)
                  for (eid, sid) in x]
    SHORTFALL_PENALTY = 10_000_00
    shortfall_terms = [shortfall[sid] * SHORTFALL_PENALTY for sid in shortfall]
    presence_penalty_terms = [val[0] * round(val[1] * 100) for val in presence_shortfall.values() if not isinstance(val[0], int)]

    model.Minimize(sum(cost_terms) + sum(shortfall_terms) + sum(presence_penalty_terms) - sum(pref_bonus_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_sec
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    assignments = []
    for shift in shifts:
        sid = shift["shift_id"]
        for eid in eligible_pairs[sid]:
            if solver.Value(x[(eid, sid)]):
                assignments.append({
                    "employee_id": eid, "name": employees[eid]["name"], "day": shift["day"],
                    "role": shift["role"], "start": fmt_time(shift["start"]), "end": fmt_time(shift["end"]),
                    "hours": shift["hours"],
                })

    gaps = [{"day": s["day"], "role": s["role"], "start": fmt_time(s["start"]), "end": fmt_time(s["end"]),
             "unfilled": solver.Value(shortfall[s["shift_id"]]), "needed": s["count_needed"]}
            for s in shifts if solver.Value(shortfall[s["shift_id"]]) > 0]

    presence_gaps = []
    for i, req in enumerate(presence_reqs):
        val = presence_shortfall.get(f"presence_{i}")
        if val is None:
            continue
        unmet = val[0] if isinstance(val[0], int) else solver.Value(val[0])
        if unmet > 0:
            presence_gaps.append({"day": req["day"], "start": fmt_time(req["start"]), "end": fmt_time(req["end"]),
                                   "pool_name": req["pool_name"], "needed": req["min_count"], "unmet": unmet})

    honored, unhonored = [], []
    for pref, candidate_keys in pref_candidates:
        assigned_key = next((k for k in candidate_keys if solver.Value(x[k])), None)
        if assigned_key:
            actual_shift = shift_lookup[assigned_key[1]]
            honored.append({**pref, "actual_start": fmt_time(actual_shift["start"]), "actual_end": fmt_time(actual_shift["end"])})
        elif candidate_keys:
            unhonored.append(pref)
        # prefs with zero candidate_keys were already warned about above; not double-counted here

    real_cost = sum(employees[eid]["hourly_rate"] * shift_lookup[sid]["hours"]
                     for (eid, sid) in x if solver.Value(x[(eid, sid)]))

    return {"assignments": assignments, "gaps": gaps, "presence_gaps": presence_gaps,
            "honored": honored, "unhonored": unhonored, "cost": real_cost}


def write_schedule(assignments, output_path):
    day_index = {d: i for i, d in enumerate(DAY_ORDER)}
    assignments_sorted = sorted(assignments, key=lambda a: (day_index[a["day"]], a["start"], a["name"]))
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["day", "start", "end", "role", "employee_id", "name", "hours"])
        w.writeheader()
        for a in assignments_sorted:
            w.writerow({"day": a["day"], "start": a["start"], "end": a["end"], "role": a["role"],
                        "employee_id": a["employee_id"], "name": a["name"], "hours": round(a["hours"], 2)})


def print_summary(employees, result):
    print("\n" + "=" * 60)
    print("SCHEDULE SUMMARY")
    print("=" * 60)
    print(f"Total shifts filled: {len(result['assignments'])}")
    print(f"Estimated weekly labor cost: ${result['cost']:,.2f}")

    hours_by_emp = defaultdict(float)
    for a in result["assignments"]:
        hours_by_emp[a["employee_id"]] += a["hours"]
    not_scheduled = [employees[eid]["name"] for eid in employees if hours_by_emp.get(eid, 0) == 0]
    print(f"People with zero hours this week: {len(not_scheduled)}")

    if result["gaps"]:
        print(f"\n⚠ {len(result['gaps'])} unfilled shift slot line(s) -- run with more --time-limit or check for understaffed roles.")
    else:
        print("\nAll required shift slots were fully staffed.")

    if result["presence_gaps"]:
        print(f"\n⚠ {len(result['presence_gaps'])} unmet presence requirement(s):")
        for g in result["presence_gaps"]:
            print(f"  {g['day']} {g['start']}-{g['end']} pool='{g['pool_name']}': {g['unmet']} short of {g['needed']}")
    total_prefs = len(result['honored']) + len(result['unhonored'])
    print(f"\nPreferred assignments honored: {len(result['honored'])} / {total_prefs}")
    for h in result["honored"]:
        print(f"  ✓ {employees[h['employee_id']]['name']} -> {h['day']} {h['role']} {h['actual_start']}-{h['actual_end']}")
    for u in result["unhonored"]:
        print(f"  ✗ {employees[u['employee_id']]['name']} -> {u['day']} {u['role']} (feasible but not chosen -- likely lost to a coverage priority elsewhere)")
    print("=" * 60 + "\n")


# ========================================================================
# Orchestration
# ========================================================================

def main():
    parser = argparse.ArgumentParser(description="Run the weekly schedule (fast path: just --new-availability + --output)")
    parser.add_argument("--new-availability", required=True, help="This week's HotSchedules availability export (always required)")
    parser.add_argument("--new-staff-export", default=None, help="Only if roster/roles changed (.numbers file)")
    parser.add_argument("--new-timecard", default=None, help="Only if refreshing pay rates / shift calibration")
    parser.add_argument("--new-targets", default=None, help="Only if department hour targets changed")
    parser.add_argument("--pools", default=None, help="Override state/pools.csv with a new file")
    parser.add_argument("--presence-requirements", default=None, help="Override state/presence_requirements.csv")
    parser.add_argument("--preferred-assignments", default=None, help="Override state/preferred_assignments.csv")
    parser.add_argument("--state-dir", default="./state")
    parser.add_argument("--output", required=True)
    parser.add_argument("--time-limit", type=int, default=120)
    args = parser.parse_args()

    ensure_dir(args.state_dir)

    log("[1/5] Converting this week's availability...")
    names_seen, name_to_id = convert_availability(args.new_availability, args.state_dir)

    roster_path = os.path.join(args.state_dir, "roster.csv")
    if args.new_staff_export:
        log("[2/5] Roster changed -- reprocessing staff export...")
        convert_staff_export(args.new_staff_export, args.state_dir, name_to_id)
    elif not os.path.exists(roster_path):
        log("ERROR: no roster.csv in state/ and no --new-staff-export provided. "
            "First run needs --new-staff-export.")
        sys.exit(1)
    else:
        log("[2/5] Roster unchanged -- reusing state/roster.csv")
    sync_roster_with_this_weeks_names(args.state_dir, names_seen, name_to_id)

    rates_path = os.path.join(args.state_dir, "hourly_rates.csv")
    shift_req_path = os.path.join(args.state_dir, "shift_requirements.csv")
    targets_path = os.path.join(args.state_dir, "targets.csv")

    if args.new_targets:
        shutil.copy(args.new_targets, targets_path)

    if args.new_timecard:
        log("[3/5] New timecard provided -- recalibrating pay rates and shift requirements...")
        fixer = build_job_title_fixer(roster_path)
        shift_rows = load_timecard_shift_rows(args.new_timecard, fixer)
        build_hourly_rates(shift_rows, args.state_dir)
        if not os.path.exists(targets_path):
            log("ERROR: --new-timecard given but no department targets available "
                "(pass --new-targets, at least on first run).")
            sys.exit(1)
        build_shift_requirements(shift_rows, targets_path, roster_path, args.state_dir)
    else:
        if not os.path.exists(rates_path) or not os.path.exists(shift_req_path):
            log("ERROR: no cached hourly_rates.csv / shift_requirements.csv in state/, "
                "and no --new-timecard provided. First run needs --new-timecard (+ --new-targets).")
            sys.exit(1)
        log("[3/5] Pay rates & shift requirements unchanged -- reusing cached versions.")

    log("[4/5] Building final employees.csv...")
    employees_path = build_employees_csv(args.state_dir)

    # optional config files: copy in overrides if given, else just use whatever's in state/ already
    pools_path = os.path.join(args.state_dir, "pools.csv")
    presence_path = os.path.join(args.state_dir, "presence_requirements.csv")
    preferred_path = os.path.join(args.state_dir, "preferred_assignments.csv")
    if args.pools:
        shutil.copy(args.pools, pools_path)
    if args.presence_requirements:
        shutil.copy(args.presence_requirements, presence_path)
    if args.preferred_assignments:
        shutil.copy(args.preferred_assignments, preferred_path)

    log("[5/5] Solving...")
    employees = load_employees_for_solver(employees_path)
    availability = load_availability_for_solver(os.path.join(args.state_dir, "availability.csv"), employees)
    shifts = load_requirements_for_solver(shift_req_path)
    pools = load_pools_for_solver(pools_path, employees)
    presence_reqs = load_presence_for_solver(presence_path)
    preferred = load_preferred_for_solver(preferred_path, employees)

    result = solve(employees, availability, shifts, pools, presence_reqs, preferred, args.time_limit)
    if result is None:
        log("No feasible solution found.")
        sys.exit(1)

    write_schedule(result["assignments"], args.output)
    log(f"\nSchedule written to: {args.output}")
    print_summary(employees, result)


if __name__ == "__main__":
    main()
