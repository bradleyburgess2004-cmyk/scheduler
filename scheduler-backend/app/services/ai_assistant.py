"""
ai_assistant.py
=================
Translates plain-English chat messages into structured actions against
the app's existing, fixed constraint catalog or a schedule-generation
request. The LLM (Anthropic Claude) never touches the database or the
solver -- it only returns plain text or one of two tool calls, each
with a narrow JSON schema that can express nothing beyond "configure
this catalog entry with these parameters" or "generate the schedule
for this week". Every actual read/write happens in plain SQLAlchemy
code here and in app/routes/ai_assistant.py, exactly like every other
route in this app.

Two entry points:
- chat_turn() -- the primary conversational flow (tool_choice="auto",
  takes prior conversation history). A valid constraint proposal is
  applied immediately (writes to restaurant_constraints and reports
  back what changed); an incomplete one becomes a clarifying question
  instead of a guess; a valid schedule-generation request is reported
  as pending and only actually run once the user clicks "Generate now"
  (POST /ai/confirm) -- generating overwrites a week's assignments and
  can take up to a couple of minutes, so it keeps an explicit
  confirmation step even though constraints no longer need one.
- interpret_prompt() -- the original single-shot, forced-tool-call,
  preview-only flow (still used by POST /ai/interpret; never writes).
"""

import os
from dataclasses import dataclass, field
from datetime import date

import anthropic

from app.models.constraint import Constraint
from app.models.restaurant_constraint import RestaurantConstraint
from app.models.role import Role
from app.models.employee import Employee

from app.optimizer.constraints.registry import CONSTRAINT_REGISTRY
from app.optimizer.constraints.param_specs import CONSTRAINT_PARAM_SPECS, IDENTITY_FIELD_TYPES

MODEL = "claude-haiku-4-5-20251001"

_client = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set in this server process's environment. "
                "If you just added it to .env, restart the backend server -- .env is only "
                "read once at process startup, and `uvicorn --reload` does not pick up "
                "changes to .env, only to .py files."
            )
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    return _client


PROPOSE_CONSTRAINT_TOOL = {
    "name": "propose_constraint",
    "description": (
        "Propose configuring one entry from this restaurant's fixed constraint "
        "catalog (given below in the system prompt). Only use a class_name that "
        "appears in that catalog -- never invent one."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "class_name": {
                "type": "string",
                "description": "Must exactly match one class_name from the constraint catalog provided in context.",
            },
            "enabled": {"type": "boolean"},
            "weight": {
                "type": ["integer", "null"],
                "description": "null = hard constraint (never violated). An integer 0-100 = soft constraint penalty weight.",
            },
            "parameter_json": {
                "type": "object",
                "description": "Keys must match the parameter spec given for this class_name. Use employee_id/role_id values from the roster given in context, never invented ones.",
            },
            "unresolved": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Plain-English notes about anything the prompt didn't specify or that couldn't be resolved (e.g. a name with no match, a missing required parameter). Empty list if nothing is unresolved.",
            },
        },
        "required": ["class_name", "enabled", "parameter_json", "unresolved"],
    },
}

PROPOSE_SCHEDULE_GENERATION_TOOL = {
    "name": "propose_schedule_generation",
    "description": "Propose generating the schedule for a specific week.",
    "input_schema": {
        "type": "object",
        "properties": {
            "week_start": {
                "type": "string",
                "description": "The resolved Monday of the requested week, as YYYY-MM-DD.",
            },
            "time_limit": {
                "type": "integer",
                "description": "Solver time limit in seconds. Default 120 if the user didn't specify one.",
            },
            "unresolved": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Plain-English notes about anything ambiguous (e.g. which week 'next week' means). Empty list if nothing is unresolved.",
            },
        },
        "required": ["week_start", "unresolved"],
    },
}


@dataclass
class ConstraintProposal:
    constraint_id: int | None
    class_name: str
    constraint_name: str | None
    existing_config_id: int | None
    enabled: bool
    weight: int | None
    parameter_json: dict
    validation_errors: list[str]
    warnings: list[str]
    action: str = field(default="configure_constraint", init=False)


@dataclass
class ScheduleGenerationProposal:
    week_start: date
    time_limit: int
    validation_errors: list[str]
    warnings: list[str]
    action: str = field(default="generate_schedule", init=False)


def _build_system_prompt(db, restaurant_id: int) -> str:
    catalog = db.query(Constraint).all()
    roles = db.query(Role).filter(Role.restaurant_id == restaurant_id).all()
    employees = (
        db.query(Employee)
        .filter(Employee.restaurant_id == restaurant_id, Employee.active.is_(True))
        .all()
    )

    catalog_lines = []
    for c in catalog:
        spec = CONSTRAINT_PARAM_SPECS.get(c.class_name, [])
        spec_desc = ", ".join(
            f"{f.key} ({f.type}{', optional' if f.optional else ''})" for f in spec
        ) or "no parameters"
        catalog_lines.append(f"- {c.class_name}: \"{c.name}\" -- {c.description}. Parameters: {spec_desc}")

    role_lines = [f"- role_id {r.role_id}: \"{r.role_name}\" (department: {r.department})" for r in roles]
    employee_lines = [
        f"- employee_id {e.employee_id}: \"{e.first_name} {e.last_name}\"" for e in employees
    ]

    return (
        "You are the natural-language interpreter for a restaurant scheduling app, "
        "talking with the user in an ongoing chat. Your job is to either (a) configure "
        "an existing constraint-catalog entry for this restaurant, or (b) generate the "
        "schedule for a specific week, by calling exactly one of the two tools provided. "
        "You may only select class_name values from the catalog below -- never invent "
        "one, never describe code, never suggest SQL.\n\n"
        "If the user's message doesn't give you enough information to fill in a "
        "constraint's required parameters, or it's ambiguous which catalog entry they "
        "mean, do NOT call a tool yet -- reply in plain conversational text asking "
        "exactly what's missing (e.g. which days, which employee, how many hours). "
        "Once you have enough information (from this message or earlier in the "
        "conversation), call the appropriate tool. Don't guess at values the user "
        "hasn't given you or implied.\n\n"
        f"Today's date is {date.today().isoformat()}. Weeks are Monday-anchored: "
        "\"this week\" means the Monday on or before today, \"next week\" means the "
        "following Monday. Constraints that take a day/days parameter (e.g. "
        "MinPositionStaffingConstraint, PreferredAssignmentConstraint, "
        "LockedAssignmentConstraint) are RECURRING weekly rules keyed by day name "
        "(\"Sat\"), not a specific calendar date -- never ask the user \"which "
        "Saturday\" for these; a day name alone is already enough information to "
        "configure them.\n\n"
        "LockedAssignmentConstraint forces a specific employee onto every shift "
        "matching its role/days/time window -- use it when the user says things like "
        "\"always put Maria on Friday grill\" or \"lock Sam into the Tuesday host "
        "shift no matter what\", as opposed to PreferredAssignmentConstraint which is "
        "just a soft nudge for softer language like \"prefer\" or \"try to\". It has "
        "the same parameter_json shape as PreferredAssignmentConstraint (days, role, "
        "employee_id, optional start_time/end_time) -- weight is ignored for it, "
        "always pass weight: null.\n\n"
        "Constraint catalog for this restaurant:\n" + "\n".join(catalog_lines) + "\n\n"
        "MinPositionStaffingConstraint's parameter_json has a nested shape, unlike every "
        "other constraint's flat key-value parameters -- match this exactly:\n"
        '{"position_type": "role" | "department", "position_value": "<exact role or '
        'department name from the roster below>", "requirements": [{"days": ["Sat"], '
        '"start_time": "17:00", "end_time": "23:00", "min_count": 5}]}\n'
        "requirements is always a list, even for a single day/time window. Use \"days\" "
        "as a list of day names in one requirement entry to apply the same minimum to "
        "several days at once, instead of adding a separate requirement entry per day. "
        "This restaurant's departments (use the exact string for a \"department\"-typed "
        "position_value): " + (", ".join(sorted({r.department for r in roles if r.department})) or "(none)") + "\n\n"
        "This restaurant's roles (use role_name string values for \"role\"-typed parameters):\n"
        + ("\n".join(role_lines) or "(none)") + "\n\n"
        "This restaurant's active employees (use the integer employee_id for "
        "\"employee\"-typed parameters):\n" + ("\n".join(employee_lines) or "(none)")
    )


def interpret_prompt(db, restaurant_id: int, prompt: str):
    system = _build_system_prompt(db, restaurant_id)
    response = get_client().messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system,
        tools=[PROPOSE_CONSTRAINT_TOOL, PROPOSE_SCHEDULE_GENERATION_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": prompt}],
    )

    tool_use = next(b for b in response.content if b.type == "tool_use")

    if tool_use.name == "propose_constraint":
        return build_constraint_proposal(db, restaurant_id, tool_use.input)
    return build_schedule_proposal(tool_use.input)


def apply_constraint_proposal(
    db, restaurant_id: int, constraint_id: int, existing_config_id: int | None,
    enabled: bool, weight: int | None, parameter_json: dict,
) -> RestaurantConstraint:
    """Writes a validated constraint proposal to restaurant_constraints --
    the only place in the AI assistant flow that performs this write.
    Callers must have already run validate_constraint_params() and
    confirmed there are no errors."""

    if existing_config_id is not None:
        db_config = (
            db.query(RestaurantConstraint)
            .filter(RestaurantConstraint.config_id == existing_config_id)
            .first()
        )
        if not db_config:
            raise ValueError(f"restaurant_constraints row {existing_config_id} not found")
        db_config.enabled = enabled
        db_config.weight = weight
        db_config.parameter_json = parameter_json
    else:
        db_config = RestaurantConstraint(
            restaurant_id=restaurant_id,
            constraint_id=constraint_id,
            enabled=enabled,
            weight=weight,
            parameter_json=parameter_json,
        )
        db.add(db_config)

    db.commit()
    db.refresh(db_config)
    return db_config


def _describe_constraint_change(
    constraint_name: str, existing_config_id: int | None, enabled: bool,
    weight: int | None, parameter_json: dict, warnings: list[str],
) -> str:
    verb = "updated" if existing_config_id is not None else "configured"
    hardness = "a hard rule (always enforced)" if weight is None else f"a soft rule (priority weight {weight})"
    params_desc = ", ".join(f"{k} = {v}" for k, v in parameter_json.items()) or "no parameters"
    status = "" if enabled else " It's currently **disabled**, so it won't affect the next generated schedule until you enable it."
    msg = f"Done — I've {verb} **{constraint_name}** as {hardness}. Parameters: {params_desc}.{status}"
    if warnings:
        msg += " Heads up: " + " ".join(warnings)
    return msg


def _describe_missing_info(validation_errors: list[str], warnings: list[str]) -> str:
    parts = list(validation_errors) + list(warnings)
    return "I need a bit more information before I can set that up: " + " ".join(parts)


def _describe_schedule_pending(week_start: date, time_limit: int, warnings: list[str]) -> str:
    msg = (
        f"I can generate the schedule for the week of {week_start.isoformat()} "
        f"(solver time limit {time_limit}s). This will overwrite any existing assignments "
        "for that week and can take up to a couple of minutes."
    )
    if warnings:
        msg += " " + " ".join(warnings)
    msg += " Click \"Generate now\" below to proceed, or tell me if you meant a different week."
    return msg


def chat_turn(db, restaurant_id: int, message: str, history: list[dict]) -> dict:
    """One turn of the AI assistant conversation. Returns a dict:
        reply: str -- what to show the user
        applied: bool -- whether a constraint was actually written this turn
        pending_schedule: {"week_start": date, "time_limit": int} | None --
            set when a valid schedule-generation request is ready but needs
            an explicit user confirmation (the frontend renders a "Generate
            now" button that calls the existing /ai/confirm endpoint)

    Unlike interpret_prompt() (single-shot, forced tool call), this uses
    tool_choice="auto" so Claude can either ask a clarifying question in
    plain text or call a tool once it has enough information -- and takes
    the prior conversation as context, so a multi-turn clarification
    ("which days?" -> "weekdays") resolves into one proposal.
    """

    system = _build_system_prompt(db, restaurant_id)
    messages = [{"role": h["role"], "content": h["content"]} for h in history]
    messages.append({"role": "user", "content": message})

    response = get_client().messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system,
        tools=[PROPOSE_CONSTRAINT_TOOL, PROPOSE_SCHEDULE_GENERATION_TOOL],
        tool_choice={"type": "auto"},
        messages=messages,
    )

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)

    if tool_use is None:
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return {"reply": text or "I'm not sure how to help with that.", "applied": False, "pending_schedule": None}

    if tool_use.name == "propose_constraint":
        proposal = build_constraint_proposal(db, restaurant_id, tool_use.input)
        if proposal.validation_errors:
            reply = _describe_missing_info(proposal.validation_errors, proposal.warnings)
            return {"reply": reply, "applied": False, "pending_schedule": None}

        apply_constraint_proposal(
            db, restaurant_id, proposal.constraint_id, proposal.existing_config_id,
            proposal.enabled, proposal.weight, proposal.parameter_json,
        )
        reply = _describe_constraint_change(
            proposal.constraint_name or proposal.class_name, proposal.existing_config_id,
            proposal.enabled, proposal.weight, proposal.parameter_json, proposal.warnings,
        )
        return {"reply": reply, "applied": True, "pending_schedule": None}

    proposal = build_schedule_proposal(tool_use.input)
    if proposal.validation_errors:
        reply = _describe_missing_info(proposal.validation_errors, proposal.warnings)
        return {"reply": reply, "applied": False, "pending_schedule": None}

    reply = _describe_schedule_pending(proposal.week_start, proposal.time_limit, proposal.warnings)
    return {
        "reply": reply,
        "applied": False,
        "pending_schedule": {"week_start": proposal.week_start, "time_limit": proposal.time_limit},
    }


def validate_constraint_params(
    db, restaurant_id: int, class_name: str, enabled: bool, weight: int | None, parameter_json: dict
) -> list[str]:
    """Shared validation used both when building a proposal for /interpret
    and when re-checking a (possibly user-edited) proposal in /confirm
    before it's written. Reuses ScheduleConstraint.validate_parameters()
    directly -- the same check the solver itself runs -- plus a check
    that any role/employee-typed parameter actually resolves for this
    restaurant."""

    errors: list[str] = []

    if class_name not in CONSTRAINT_REGISTRY:
        return [f"'{class_name}' is not a known constraint."]

    try:
        CONSTRAINT_REGISTRY[class_name](
            restaurant_id=restaurant_id,
            enabled=enabled,
            weight=weight,
            parameters=parameter_json,
        )
    except ValueError as exc:
        errors.append(str(exc))

    roles_by_name = {
        r.role_name: r.role_id
        for r in db.query(Role).filter(Role.restaurant_id == restaurant_id).all()
    }
    employee_ids = {
        e.employee_id
        for e in db.query(Employee).filter(Employee.restaurant_id == restaurant_id).all()
    }
    for spec in CONSTRAINT_PARAM_SPECS.get(class_name, []):
        if spec.key not in parameter_json:
            continue
        value = parameter_json[spec.key]
        if spec.type == "role" and value not in roles_by_name:
            errors.append(f"'{value}' does not match any role for this restaurant.")
        elif spec.type == "employee" and value not in employee_ids:
            errors.append(f"employee_id {value!r} does not match any employee for this restaurant.")
        elif spec.type == "employee_pairs":
            for pair in (value or []):
                for eid in pair:
                    if eid not in employee_ids:
                        errors.append(f"employee_id {eid!r} does not match any employee for this restaurant.")

    return errors


# The Constraints page lets a manager add as many rows as they want for any
# parameterized constraint -- one per employee, per day, per role, etc. (see
# Constraints.tsx's "+ Add rule"). So when the AI assistant proposes
# configuring a constraint, "the existing row to update" can't just be
# "the one row for this restaurant/constraint_id" anymore -- it has to
# disambiguate by whichever parameter(s) actually identify a specific rule,
# or it would silently overwrite an unrelated employee's/day's/role's rule
# instead of adding a new one.
#
# Only classes with NO identifying parameter (a plain number/boolean knob
# like "max 5 consecutive days") are true singletons -- at most one row per
# restaurant makes sense for those, so they keep the old rows[0] behavior.
# MinPositionStaffingConstraint is the one explicit override: its identifying
# field (position_value) is typed "text" like several non-identifying fields
# on other classes, so it can't be inferred purely from field type.
_EXPLICIT_DISAMBIGUATION_KEYS = {
    "MinPositionStaffingConstraint": ["position_value"],
}
_IDENTITY_FIELD_TYPES = IDENTITY_FIELD_TYPES


def _find_existing_restaurant_constraint(db, restaurant_id, catalog_row, class_name, parameter_json):
    rows = (
        db.query(RestaurantConstraint)
        .filter(
            RestaurantConstraint.restaurant_id == restaurant_id,
            RestaurantConstraint.constraint_id == catalog_row.constraint_id,
        )
        .all()
    )
    fields = CONSTRAINT_PARAM_SPECS.get(class_name, [])
    identity_keys = _EXPLICIT_DISAMBIGUATION_KEYS.get(class_name) or [
        f.key for f in fields if f.type in _IDENTITY_FIELD_TYPES
    ]
    if not identity_keys:
        return rows[0] if rows else None

    for row in rows:
        existing_params = row.parameter_json or {}
        if all(existing_params.get(k) == parameter_json.get(k) for k in identity_keys):
            return row
    return None


def build_constraint_proposal(db, restaurant_id: int, ai_input: dict) -> ConstraintProposal:
    class_name = ai_input.get("class_name")
    enabled = bool(ai_input.get("enabled", True))
    weight = ai_input.get("weight")
    parameter_json = ai_input.get("parameter_json") or {}
    warnings = list(ai_input.get("unresolved") or [])
    validation_errors: list[str] = []

    if class_name not in CONSTRAINT_REGISTRY:
        return ConstraintProposal(
            constraint_id=None,
            class_name=class_name or "",
            constraint_name=None,
            existing_config_id=None,
            enabled=enabled,
            weight=weight,
            parameter_json=parameter_json,
            validation_errors=[f"'{class_name}' is not a known constraint."],
            warnings=warnings,
        )

    catalog_row = db.query(Constraint).filter(Constraint.class_name == class_name).first()
    if catalog_row is None:
        validation_errors.append(f"'{class_name}' has no catalog row in the database.")

    existing = None
    if catalog_row is not None:
        existing = _find_existing_restaurant_constraint(db, restaurant_id, catalog_row, class_name, parameter_json)

    validation_errors.extend(
        validate_constraint_params(db, restaurant_id, class_name, enabled, weight, parameter_json)
    )

    return ConstraintProposal(
        constraint_id=catalog_row.constraint_id if catalog_row else None,
        class_name=class_name,
        constraint_name=catalog_row.name if catalog_row else None,
        existing_config_id=existing.config_id if existing else None,
        enabled=enabled,
        weight=weight,
        parameter_json=parameter_json,
        validation_errors=validation_errors,
        warnings=warnings,
    )


def build_schedule_proposal(ai_input: dict) -> ScheduleGenerationProposal:
    warnings = list(ai_input.get("unresolved") or [])
    validation_errors: list[str] = []
    time_limit = int(ai_input.get("time_limit") or 120)

    raw_week_start = ai_input.get("week_start")
    week_start = None
    try:
        week_start = date.fromisoformat(raw_week_start)
    except (TypeError, ValueError):
        validation_errors.append(f"Could not parse a valid date from '{raw_week_start}'.")

    if week_start is not None and week_start.weekday() != 0:
        snapped = date.fromordinal(week_start.toordinal() - week_start.weekday())
        warnings.append(
            f"'{raw_week_start}' isn't a Monday -- snapped to the Monday of that week ({snapped.isoformat()})."
        )
        week_start = snapped

    return ScheduleGenerationProposal(
        week_start=week_start or date.today(),
        time_limit=time_limit,
        validation_errors=validation_errors,
        warnings=warnings,
    )
