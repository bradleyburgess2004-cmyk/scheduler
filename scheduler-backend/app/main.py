from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app import models
from app.routes import employees
from app.routes import restaurants
from app.routes import roles
from app.routes import skills
from app.routes import employee_skills
from app.routes import availability
from app.routes import time_off_requests
from app.routes import shift_templates
from app.routes import shifts
from app.routes import assignments
from app.routes import constraints
from app.routes import restaurant_constraints
from app.routes import employee_roles
from app.routes import department_targets
from app.routes import schedule
from app.routes import availability_upload
from app.routes import labor_analytics
from app.routes import ai_assistant
from app.routes import time_off_upload
from app.routes import training_data
from app.routes import schedule_template_upload

# Create all tables (temporary for development)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Scheduler API",
    description="Backend API for the AI Restaurant Scheduling Platform",
    version="0.1.0"
)

# Allow any local Vite dev server to call this API during frontend
# development -- matched by regex rather than a fixed port, since Vite
# auto-increments to 5174/5175/etc. whenever 5173 is already taken (e.g.
# a second `npm run dev` left running). Add the real deployed frontend
# origin explicitly to allow_origins once one exists.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(employees.router)
app.include_router(restaurants.router)
app.include_router(roles.router)
app.include_router(skills.router)
app.include_router(employee_skills.router)
app.include_router(availability.router)
app.include_router(time_off_requests.router)
app.include_router(shift_templates.router)
app.include_router(shifts.router)
app.include_router(assignments.router)
app.include_router(constraints.router)
app.include_router(restaurant_constraints.router)
app.include_router(employee_roles.router)
app.include_router(department_targets.router)
app.include_router(schedule.router)
app.include_router(availability_upload.router)
app.include_router(labor_analytics.router)
app.include_router(ai_assistant.router)
app.include_router(time_off_upload.router)
app.include_router(training_data.router)
app.include_router(schedule_template_upload.router)


@app.get("/")
def root():
    return {
        "message": "AI Scheduler API is running!"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }