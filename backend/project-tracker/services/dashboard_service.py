"""One call that returns everything a role's home page shows."""

from datetime import date, timedelta

import config
from db import Database
from models.entities import User
from repositories.audit_repository import AuditRepository
from repositories.milestone_repository import MilestoneRepository
from repositories.project_repository import ProjectRepository
from repositories.time_entry_repository import TimeEntryRepository
from repositories.user_repository import UserRepository
from services.common import milestone_status, week_of
from services.milestones_service import serialize_assignment
from services.projects_service import serialize_project
from services.time_service import serialize_entry
from services.users_service import serialize_many


def _projects(db: Database, viewer: User) -> list[dict]:
    visibility, params = viewer.project_filter()
    return [serialize_project(db, row, viewer) for row in ProjectRepository(db).search(visibility, params)]


def _due_soon(db: Database, viewer: User, days: int = 14) -> list[dict]:
    visibility, params = viewer.project_filter()
    rows = db.all(
        "SELECT m.*, p.title AS project_title FROM milestones m JOIN projects p ON p.id = m.project_id "
        f"WHERE {visibility} AND p.archived_at IS NULL AND m.completed_at IS NULL AND m.end_date <= %s "  # noqa: S608 - role filter
        "ORDER BY m.end_date LIMIT 20",
        [*params, date.today() + timedelta(days=days)],
    )
    return [{"id": r["id"], "title": r["title"], "project_id": r["project_id"], "project_title": r["project_title"],
             "end_date": r["end_date"], "status": milestone_status(r), "overdue": r["end_date"] < date.today()}
            for r in rows]


def dashboard(db: Database, viewer: User) -> dict:
    if viewer.role == "employee":
        return _employee(db, viewer)
    projects = _projects(db, viewer)
    team_rows = UserRepository(db).search(archived=False, role="employee",
                                          manager_id=viewer.id if viewer.role == "manager" else None)
    team = serialize_many(db, team_rows, viewer)
    data = {
        "role": viewer.role,
        "summary": {
            "active_projects": len([p for p in projects if not p["completed_at"]]),
            "at_risk_projects": len([p for p in projects if p["at_risk"]]),
            "over_budget_projects": len([p for p in projects if p["health"] == "red"]),
            "team_size": len(team),
            "unassigned_employees": len([m for m in team if not m.get("current_assignment")]),
        },
        "projects": projects,
        "team": team,
        "upcoming_milestones": _due_soon(db, viewer),
    }
    if viewer.role == "admin":
        data["counts"] = db.one(
            """
            SELECT COUNT(*) FILTER (WHERE role = 'admin' AND archived_at IS NULL)    AS admins,
                   COUNT(*) FILTER (WHERE role = 'manager' AND archived_at IS NULL)  AS managers,
                   COUNT(*) FILTER (WHERE role = 'employee' AND archived_at IS NULL) AS employees,
                   COUNT(archived_at)                                                AS archived_users
            FROM users
            """
        )
        data["recent_activity"] = AuditRepository(db).recent()
    return data


def _employee(db: Database, viewer: User) -> dict:
    today = date.today()
    monday, sunday = week_of(today)
    entries = TimeEntryRepository(db).search(["t.employee_id = %s", "t.work_date BETWEEN %s AND %s"],
                                             [viewer.employee_id, monday, sunday])
    by_day = {e["work_date"]: float(e["hours"]) for e in entries}
    days = [{"date": monday + timedelta(days=i), "hours": by_day.get(monday + timedelta(days=i), 0)} for i in range(7)]
    total = sum(by_day.values())

    assignments = MilestoneRepository(db).search_assignments(
        ["a.employee_id = %s", "a.end_date >= CURRENT_DATE", "p.archived_at IS NULL"], [viewer.employee_id])
    current = next((a for a in assignments if a["start_date"] <= today), None)
    return {
        "role": "employee",
        "current_assignment": serialize_assignment(current) if current else None,
        "upcoming_assignments": [serialize_assignment(a) for a in assignments if a is not current],
        "week": {"start": monday, "end": sunday, "days": days, "total_hours": total,
                 "target_hours": config.HOURS_PER_WEEK, "remaining_hours": max(config.HOURS_PER_WEEK - total, 0),
                 "logged_today": today in by_day},
        "projects": _projects(db, viewer),
        "recent_entries": [serialize_entry(e, viewer) for e in
                           TimeEntryRepository(db).search(["t.employee_id = %s"], [viewer.employee_id], limit=10)],
    }
