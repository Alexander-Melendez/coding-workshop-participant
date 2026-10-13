"""Lookups and small helpers shared by several services."""

from datetime import date, timedelta

from db import Database
from errors import BadRequest, Conflict, Forbidden, NotFound
from models.entities import User
from repositories.milestone_repository import MilestoneRepository
from repositories.project_repository import ProjectRepository


def business_days(start: date, end: date) -> int:
    """Number of Monday-Friday days from start to end, inclusive (0 if start > end)."""
    days = 0
    day = start
    while day <= end:
        if day.weekday() < 5:
            days += 1
        day += timedelta(days=1)
    return days


def week_of(day: date) -> tuple[date, date]:
    """Monday and Sunday of the week containing `day`."""
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def check_date_order(start: date, end: date, field: str = "end_date") -> None:
    if end < start:
        raise BadRequest("The end date must be on or after the start date",
                         {field: "Must be on or after the start date"})


def number(value) -> float:
    """SUM() returns None when there are no rows; treat that as 0."""
    return float(value) if value is not None else 0.0


# --- projects ---------------------------------------------------------------
def project_for(db: Database, user: User, project_id: int, manage: bool = False) -> dict:
    """Load a project the user may see (or manage). Archived projects are hidden from non-admins."""
    projects = ProjectRepository(db)
    project = projects.find_by_id(project_id)
    if project is None or (project["archived_at"] and not user.can_see_archived):
        raise NotFound("Project not found")
    assigned = projects.is_assigned(project_id, user.employee_id)
    if not user.can_view_project(project, assigned):
        raise Forbidden("You don't have access to this project")
    if manage and not user.can_manage_project(project):
        raise Forbidden("Only this project's manager or an admin can change it")
    return project


def ensure_project_open(project: dict) -> None:
    """Archived and completed projects are read-only."""
    if project["archived_at"]:
        raise Conflict("This project is archived and read-only")
    if project["completed_at"]:
        raise Conflict("This project is completed and read-only")


# --- milestones -------------------------------------------------------------
def milestone_for(db: Database, user: User, milestone_id: int, manage: bool = False) -> tuple[dict, dict]:
    """Load a milestone and its project, checking the user's access to the project."""
    milestone = MilestoneRepository(db).find_by_id(milestone_id)
    if milestone is None:
        raise NotFound("Milestone not found")
    return milestone, project_for(db, user, milestone["project_id"], manage)


def ensure_milestone_open(milestone: dict) -> None:
    """Completed milestones are locked."""
    if milestone["completed_at"]:
        raise Conflict("This milestone is complete and locked")


def milestone_status(milestone: dict, today: date | None = None) -> str:
    """Derived from the timestamps and dates: complete, in_progress or not_started."""
    today = today or date.today()
    if milestone["completed_at"]:
        return "complete"
    if milestone["start_date"] <= today:
        return "in_progress"
    return "not_started"
