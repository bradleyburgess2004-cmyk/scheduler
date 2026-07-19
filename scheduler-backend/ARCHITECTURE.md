# Restaurant Scheduler System — Architecture & Roadmap

This is the long-term target architecture, reconciled against what's
actually built as of 2026-07-13. Anything marked **(future)** is vision,
not implemented — don't assume it exists when planning new work.

## Target architecture

```
                                RESTAURANT SCHEDULER SYSTEM
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         USERS                                                    │
│──────────────────────────────────────────────────────────────────────────────────────────────────│
│ Restaurant Owner │ Manager │ Shift Lead │ Employee                                               │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                │ HTTPS
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    FRONTEND (React + TS)  (future)                                │
│──────────────────────────────────────────────────────────────────────────────────────────────────│
│ Dashboard │ Employee Management │ Availability Calendar │ Schedule Calendar (Drag & Drop)          │
│ CSV Upload │ Labor Analytics │ Settings                                                           │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                │ REST API / JSON
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   FASTAPI BACKEND                                                 │
│──────────────────────────────────────────────────────────────────────────────────────────────────│
│ Authentication (future) │ Employee API ✓ │ Availability API ✓ │ Schedule API (future)              │
│ CSV Import API (future — currently a CLI script) │ Forecast API (future) │ Optimization API (future)│
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
         │                  │                    │                    │                   │
         ▼                  ▼                    ▼                    ▼                   ▼
 ┌──────────────┐   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   ┌────────────────┐
 │ CSV Importer │   │ Data Validator│   │ ORM Layer ✓  │    │ Auth Service │   │ AI Scheduler   │
 │ (CLI script) │   │ (inline)      │   │ SQLAlchemy   │    │ (future)     │   │ OR-Tools ✓*    │
 └──────────────┘   └──────────────┘    └──────────────┘    └──────────────┘   └────────────────┘
                                                │
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   POSTGRESQL DATABASE (scheduler_db)                              │
│──────────────────────────────────────────────────────────────────────────────────────────────────│
│ restaurants ✓ │ employees ✓ │ roles ✓ │ employee_roles ✓ (M:N, not in original diagram)            │
│ availability ✓ (was "employee_availability") │ shift_templates ✓ (was "shift_requirements")        │
│ shifts ✓ │ assignments ✓ (together ≈ "scheduled_shifts") │ department_targets ✓ (not in orig. diagram)│
│ skills / employee_skills / time_off_requests / constraints / restaurant_constraints — schema exists,│
│   currently empty, unused by real data                                                             │
│ schedules ✗ │ employee_preferences ✗ │ sales_history ✗ (future) │ import_history ✗                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                │
                           ┌────────────────────┴─────────────────────┐
                           ▼                                          ▼
              Historical Sales Data (future)                Schedule History (future)
                           │                                          │
                           └────────────────────┬─────────────────────┘
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             OPTIMIZATION & ML ENGINE                                              │
│──────────────────────────────────────────────────────────────────────────────────────────────────│
│ Demand Forecasting (future) — XGBoost / Prophet                                                   │
│ Scheduling Optimizer ✓* — OR-Tools CP-SAT, labor cost minimization, availability constraints,      │
│   overtime constraints, fairness balancing, preference scoring                                    │
│ Output → Weekly Schedule (currently a CSV file, not a DB write)                                    │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                │
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               EXTERNAL INTEGRATIONS (future)                                       │
│──────────────────────────────────────────────────────────────────────────────────────────────────│
│ HotSchedules │ Toast POS │ Square │ 7shifts │ ADP Payroll │ Email │ SMS │ Push Notifications        │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

`✓*` = exists, but isolated: the OR-Tools solver lives entirely in
`weekly_workflow/run_week.py`, a standalone CLI/Flask tool. It reads its
own CSVs, not `scheduler_db`, and writes its output to a CSV file, never
to the database. It is not reachable from the FastAPI backend at all
today.

## Table name reconciliation

The original diagram's DB table names don't all match what's actually in
`scheduler_db`. Use the right-hand column going forward:

| Diagram said | Actual table | Status |
|---|---|---|
| `restaurants` | `restaurants` | ✓ matches |
| `employees` | `employees` | ✓ matches (see real columns below) |
| `roles` | `roles` | ✓ matches |
| `employee_availability` | `availability` | renamed |
| `shift_requirements` | `shift_templates` | renamed + extended (`day_of_week`, `required_count` added specifically to hold the weekly requirement shape) |
| `schedules` | *(none)* | not implemented — no table represents "a generated schedule" as its own entity |
| `scheduled_shifts` | `shifts` + `assignments` | split across two tables: `shifts` = a specific dated shift instance, `assignments` = which employee is on it |
| `employee_preferences` | *(none)* | not implemented — `weekly_workflow`'s `preferred_assignments.csv`/`pools.csv`/`presence_requirements.csv` concepts are not imported into the DB |
| `sales_history` | *(none)* | correctly future — no forecasting data source yet |
| `import_history` | *(none)* | not implemented — no audit log of CSV import runs (files, timestamp, row counts, warnings) |

Real tables **not mentioned** in the original diagram at all:
- `employee_roles` — many-to-many employee↔role (233 real employees hold
  multiple job functions; the diagram's single `employees → roles` arrow
  undersells this)
- `department_targets` — department-level weekly hour budgets, imported
  from `targets.csv`
- `skills`, `employee_skills`, `time_off_requests`, `constraints`,
  `restaurant_constraints` — schema exists (built for an earlier dummy
  dataset), currently **empty**, not used by the real Dwarf House data

Real `employees` columns, for reference: `employee_id`, `restaurant_id`,
`first_name`, `last_name`, `role_id` (single *primary* role — first role
listed in the source CSV; full role set lives in `employee_roles`),
`hourly_rate`, `hire_date`, `active`, `max_weekly_hours`,
`overtime_limit`, `external_employee_id` (stable CSV-import key),
`min_weekly_hours`.

## Data flow reconciliation

Original:
```
CSV Upload / POS Integration → Import & Validation → PostgreSQL →
Load Employees + Availability + Shift Requirements + Preferences →
OR-Tools Optimizer → Generated Weekly Schedule → Save to Database →
React Calendar / Employee App
```

Actual, today:
```
CSV files (manually exported from HotSchedules) →
  python -m app.scripts.import_weekly_workflow  (CLI, not an API; no POS integration) →
PostgreSQL (scheduler_db) →
  Employees + Availability + Shift Templates + Department Targets load fine via the API
  (Preferences/pools/presence-requirements are NOT in the DB — still flat CSVs) →
[GAP] OR-Tools optimizer runs separately, reading weekly_workflow's own CSV state —
  it never reads from scheduler_db and never writes back to it →
Weekly schedule CSV file (downloaded from the Flask UI or CLI output) →
[GAP] no calendar UI exists; nothing is saved back to shifts/assignments
```

The single biggest gap between "what's built" and "what the diagram
promises" is the optimizer disconnect: it's a fully working solver, just
not wired to the database or the FastAPI app. Closing that (optimizer
reads employees/availability/shift_templates from Postgres, writes its
result into `shifts` + `assignments`) is the natural next milestone
before frontend or auth work, since everything downstream of it
(calendar UI, notifications) depends on schedules actually landing in
the DB.

## Scaffolding already in place

`app/importer/`, `app/optimizer/`, `app/services/` exist as empty
directories — no code yet, but they're reasonable homes for: turning the
CSV import script into a real API + `import_history` audit table
(`app/importer/`), wiring the OR-Tools solver to `scheduler_db`
(`app/optimizer/`), and an auth/business-logic layer (`app/services/`).

## Not yet started, confirmed by direct inspection

- **Authentication**: no JWT/OAuth/login code anywhere in `app/`.
- **Frontend**: no React project exists anywhere on disk.
- **CSV Import API / Data Validator**: exists as a CLI script
  (`app/scripts/import_weekly_workflow.py`) with inline validation
  (duplicate-ID detection, orphan checks, unmatched-role checks) — not a
  FastAPI endpoint or a standalone validator module.
- **Forecasting, POS/payroll integrations**: none started — correctly
  marked future in the original diagram already.
