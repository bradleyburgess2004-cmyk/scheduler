import anthropic

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.restaurant import Restaurant
from app.models.constraint import Constraint
from app.models.restaurant_constraint import RestaurantConstraint

from app.optimizer.scheduler import solve_schedule
from app.optimizer.scheduler import save_assignments

from app.schemas.ai_assistant import AiInterpretRequest
from app.schemas.ai_assistant import AiInterpretResponse
from app.schemas.ai_assistant import AiConfirmConstraintRequest
from app.schemas.ai_assistant import AiConfirmScheduleRequest
from app.schemas.ai_assistant import AiChatRequest
from app.schemas.ai_assistant import AiChatResponse
from app.schemas.restaurant_constraint import RestaurantConstraintResponse
from app.schemas.schedule import GenerateScheduleResponse

from app.services import ai_assistant

router = APIRouter(
    prefix="/restaurants",
    tags=["AI Assistant"],
)


def _get_restaurant_or_404(restaurant_id: int, db: Session) -> Restaurant:
    restaurant = db.query(Restaurant).filter(Restaurant.restaurant_id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant


@router.post("/{restaurant_id}/ai/interpret", response_model=AiInterpretResponse)
def interpret(restaurant_id: int, body: AiInterpretRequest, db: Session = Depends(get_db)):
    """Translates a plain-English prompt into a structured proposal.
    Read-only: never writes to the database and never runs the solver."""

    _get_restaurant_or_404(restaurant_id, db)

    try:
        proposal = ai_assistant.interpret_prompt(db, restaurant_id, body.prompt)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except anthropic.AuthenticationError:
        raise HTTPException(
            status_code=502,
            detail="The AI assistant couldn't authenticate with Anthropic -- check that "
                   "ANTHROPIC_API_KEY is set correctly and the backend server has been "
                   "restarted since it was added (a running server only reads .env once, at startup).",
        )
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"The AI assistant is unavailable right now: {exc}")

    return AiInterpretResponse(proposal=proposal)


@router.post("/{restaurant_id}/ai/chat", response_model=AiChatResponse)
def chat(restaurant_id: int, body: AiChatRequest, db: Session = Depends(get_db)):
    """One turn of the conversational AI assistant. A valid constraint
    request is applied immediately and reported back; an incomplete one
    gets a clarifying question instead; a valid schedule-generation
    request comes back as `pending_schedule` for the frontend to confirm
    via POST /ai/confirm (generating overwrites a week's assignments and
    can take a couple of minutes, so it keeps its own confirm step)."""

    _get_restaurant_or_404(restaurant_id, db)

    try:
        result = ai_assistant.chat_turn(
            db, restaurant_id, body.message, [h.model_dump() for h in body.history]
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except anthropic.AuthenticationError:
        raise HTTPException(
            status_code=502,
            detail="The AI assistant couldn't authenticate with Anthropic -- check that "
                   "ANTHROPIC_API_KEY is set correctly and the backend server has been "
                   "restarted since it was added (a running server only reads .env once, at startup).",
        )
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"The AI assistant is unavailable right now: {exc}")

    return AiChatResponse(**result)


@router.post("/{restaurant_id}/ai/confirm")
def confirm(
    restaurant_id: int,
    body: AiConfirmConstraintRequest | AiConfirmScheduleRequest,
    db: Session = Depends(get_db),
):
    """Applies a proposal the user has already reviewed and confirmed --
    the only endpoint in the AI assistant flow that writes anything."""

    _get_restaurant_or_404(restaurant_id, db)

    if body.action == "configure_constraint":
        catalog_row = db.query(Constraint).filter(Constraint.constraint_id == body.constraint_id).first()
        if not catalog_row:
            raise HTTPException(status_code=404, detail="Constraint not found")

        errors = ai_assistant.validate_constraint_params(
            db, restaurant_id, catalog_row.class_name, body.enabled, body.weight, body.parameter_json
        )
        if errors:
            raise HTTPException(status_code=422, detail=errors)

        if body.existing_config_id is not None:
            existing = (
                db.query(RestaurantConstraint)
                .filter(RestaurantConstraint.config_id == body.existing_config_id)
                .first()
            )
            if not existing:
                raise HTTPException(status_code=404, detail="Restaurant constraint not found")

        db_config = ai_assistant.apply_constraint_proposal(
            db, restaurant_id, body.constraint_id, body.existing_config_id,
            body.enabled, body.weight, body.parameter_json,
        )
        return RestaurantConstraintResponse.model_validate(db_config)

    result = solve_schedule(db, restaurant_id, body.week_start, body.time_limit)
    if result is None:
        raise HTTPException(
            status_code=422,
            detail="No feasible schedule could be generated for this week with the current "
                   "constraints and availability. Try relaxing a constraint or check that shift "
                   "templates are configured.",
        )

    saved = save_assignments(db, result)
    return GenerateScheduleResponse(
        restaurant_id=restaurant_id,
        week_start=body.week_start,
        assignments_saved=saved,
        total_cost=round(result["cost"], 2),
        understaffed_shifts=len(result["gaps"]),
    )
