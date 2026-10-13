"""Projects: create (admin), edit and complete (its manager or an admin), archive (admin).

completed_at and archived_at are the flags:
    archived_at set           -> archived (only admins see it)
    completed_at set          -> completed (read-only)
    both NULL                 -> in progress

Colour shown in the UI ("health"):
    green  completed or archived
    red    in progress and spent more than the budget
    white  in progress and within budget
"""

from datetime import date, timedelta
from decimal import Decimal

from db import Database
from errors import BadRequest, Conflict, NotFound
from models.entities import User, display_id, hourly_rate
from models.schemas import ManagerChange, ProjectCreate, ProjectUpdate
from repositories.audit_repository import AuditRepository
from repositories.project_repository import ProjectRepository
from repositories.user_repository import UserRepository
from services.common import (
    business_days,
    check_date_order,
    ensure_project_open,
    number,
    project_for,
)


def _check_manager(db: Database, manager_id: int) -> None:
    manager = UserRepository(db).find_by_id(manager_id)
    if manager is None or manager["role"] != "manager" or manager["archived_at"]:
        raise BadRequest("Choose an active manager", {"manager_id": "Must be an active manager"})


# --- numbers ----------------------------------------------------------------
def summary(db: Database, project: dict, today: date | None = None) -> dict:
    """Hours, money, forecast, milestone progress, colour and risk for one project.

    forecast = spent so far + (remaining assigned weekdays from tomorrow x 8h x hourly rate)
    """
    today = today or date.today()
    projects = ProjectRepository(db)
    logged = projects.hours_and_spent(project["id"])
    hours, spent = number(logged["hours"]), number(logged["spent"])

    assigned_hours = 0.0
    assigned_cost = 0.0
    for a in projects.open_assignments(project["id"]):
        days_left = business_days(max(a["start_date"], today + timedelta(days=1)), a["end_date"])
        assigned_hours += days_left * 8
        assigned_cost += days_left * 8 * float(hourly_rate(a["salary"]))

    milestones = projects.milestone_dates(project["id"])
    total = len(milestones)
    done = len([m for m in milestones if m["completed_at"]])
    overdue = len([m for m in milestones if not m["completed_at"] and m["end_date"] < today])

    budget = float(project["budget"])
    forecast = spent + assigned_cost
    if project["completed_at"] or project["archived_at"]:
        health = "green"
    elif spent > budget:
        health = "red"
    else:
        health = "white"

    reasons = []
    if not project["completed_at"] and not project["archived_at"]:
        if spent > budget:
            reasons.append("Over budget")
        elif forecast > budget:
            reasons.append("Forecast cost exceeds budget")
        if overdue:
            reasons.append(f"{overdue} overdue milestone{'s' if overdue != 1 else ''}")
        if project["end_date"] < today:
            reasons.append("Past the project end date")
        estimate = float(project["estimated_hours"])
        if estimate and hours + assigned_hours > estimate:
            reasons.append("Planned hours exceed the estimate")

    return {
        "hours_logged": hours,
        "hours_assigned": assigned_hours,
        "spent": spent,
        "forecast": forecast,
        "remaining": budget - spent,
        "budget_used_pct": round(spent / budget * 100) if budget else 0,
        "milestones_total": total,
        "milestones_completed": done,
        "milestones_overdue": overdue,
        "progress_pct": round(done / total * 100) if total else 0,
        "health": health,
        "at_risk": bool(reasons),
        "risk_reasons": reasons,
    }


MONEY_FIELDS = ("budget", "spent", "forecast", "remaining", "budget_used_pct")


def serialize_project(db: Database, project: dict, viewer: User) -> dict:
    """Project for the API. Employees don't see any money."""
    data = {
        "id": project["id"],
        "title": project["title"],
        "description": project["description"],
        "start_date": project["start_date"],
        "end_date": project["end_date"],
        "budget": project["budget"],
        "estimated_hours": project["estimated_hours"],
        "manager": {"id": project["manager_id"], "name": project["manager_name"],
                    "display_id": display_id("manager", project["manager_id"])},
        "completed_at": project["completed_at"],
        "archived_at": project["archived_at"],
        "created_at": project["created_at"],
        **summary(db, project),
    }
    if not viewer.can_see_costs:
        for field in MONEY_FIELDS:
            data.pop(field)
    return data


def _detail(db: Database, viewer: User, project_id: int) -> dict:
    """Project plus what the viewer may do with it and (for staff) the team's hours and cost."""
    project = ProjectRepository(db).find_by_id(project_id)
    data = serialize_project(db, project, viewer)
    is_open = not project["completed_at"] and not project["archived_at"]
    can_manage = viewer.can_manage_project(project)
    all_done = data["milestones_total"] > 0 and data["milestones_completed"] == data["milestones_total"]
    data["permissions"] = {
        "can_edit": can_manage and is_open,
        "can_manage_milestones": can_manage and is_open,
        "can_complete": can_manage and is_open and all_done,
        "can_archive": viewer.can_see_archived and bool(project["completed_at"]) and not project["archived_at"],
        "can_restore": viewer.can_see_archived and bool(project["archived_at"]),
        "can_change_manager": viewer.can_create_projects,
        "can_view_costs": viewer.can_see_costs,
        "can_log_time": viewer.can_log_time and is_open,
    }
    if viewer.can_see_costs:
        team = []
        for member in ProjectRepository(db).team(project_id):
            item = {"id": member["id"], "display_id": display_id("employee", member["id"]), "name": member["name"],
                    "archived": member["archived_at"] is not None, "hours": number(member["hours"])}
            # Per-person cost reveals salary: only for people whose salary the viewer may see
            if viewer.can_view_salary(member):
                item["cost"] = number(member["cost"])
            team.append(item)
        data["team"] = team
    return data


# ---------------------------------------------------------------------------
def list_projects(db: Database, viewer: User, search: str | None, state: str | None,
                  health: str | None, at_risk: bool) -> list[dict]:
    if state in ("archived", "all") and not viewer.can_see_archived:
        state = None
    visibility, params = viewer.project_filter()
    rows = ProjectRepository(db).search(visibility, params, state=state, text=search)
    projects = [serialize_project(db, row, viewer) for row in rows]
    if health:
        projects = [p for p in projects if p["health"] == health]
    if at_risk:
        projects = [p for p in projects if p["at_risk"]]
    return projects


def create_project(db: Database, actor: User, body: ProjectCreate) -> dict:
    check_date_order(body.start_date, body.end_date)
    _check_manager(db, body.manager_id)
    projects = ProjectRepository(db)
    project_id = projects.create(body.model_dump())
    projects.add_budget_change(project_id, 0, body.budget, "Starting budget", actor.id)
    AuditRepository(db).add(actor, "create", "project", project_id, f"Created project {body.title}",
                            after=projects.find_by_id(project_id))
    return _detail(db, actor, project_id)


def get_project(db: Database, viewer: User, project_id: int) -> dict:
    project_for(db, viewer, project_id)
    return _detail(db, viewer, project_id)


def update_project(db: Database, actor: User, project_id: int, body: ProjectUpdate) -> dict:
    """Edit info, dates or budget. A budget change needs a reason and is saved in the history."""
    project = project_for(db, actor, project_id, manage=True)
    ensure_project_open(project)
    changes = body.model_dump(include=body.model_fields_set - {"budget_change_reason"})
    if not changes:
        raise BadRequest("Nothing to update")
    if "title" in changes and not changes["title"]:
        raise BadRequest("The title can't be empty", {"title": "This field is required"})
    new = {**project, **{k: v for k, v in changes.items() if v is not None or k == "description"}}
    check_date_order(new["start_date"], new["end_date"])

    for m in ProjectRepository(db).milestone_dates(project_id):
        if m["start_date"] < new["start_date"] or m["end_date"] > new["end_date"]:
            raise BadRequest(f"Milestone '{m['title']}' falls outside these dates. Change it first.",
                             {"start_date": "Must include every milestone", "end_date": "Must include every milestone"})

    budget_changed = Decimal(new["budget"]) != Decimal(project["budget"])
    if budget_changed and not body.budget_change_reason:
        raise BadRequest("Explain why the budget is changing",
                         {"budget_change_reason": "Required when the budget changes"})

    projects = ProjectRepository(db)
    projects.update(project_id, new)
    audit = AuditRepository(db)
    if budget_changed:
        projects.add_budget_change(project_id, project["budget"], new["budget"], body.budget_change_reason, actor.id)
        audit.add(actor, "budget_change", "project", project_id,
                  f"Budget for {new['title']}: {project['budget']} -> {new['budget']} ({body.budget_change_reason})")
    audit.add(actor, "update", "project", project_id, f"Updated project {new['title']}",
              project, projects.find_by_id(project_id))
    return _detail(db, actor, project_id)


def complete_project(db: Database, actor: User, project_id: int) -> dict:
    """Only when every milestone is complete."""
    project = project_for(db, actor, project_id, manage=True)
    ensure_project_open(project)
    milestones = ProjectRepository(db).milestone_dates(project_id)
    if not milestones:
        raise Conflict("Add and complete at least one milestone first")
    open_ones = [m for m in milestones if not m["completed_at"]]
    if open_ones:
        raise Conflict(f"{len(open_ones)} of {len(milestones)} milestones aren't complete yet")
    ProjectRepository(db).mark_completed(project_id)
    AuditRepository(db).add(actor, "complete", "project", project_id, f"Completed project {project['title']}")
    return _detail(db, actor, project_id)


def archive_project(db: Database, actor: User, project_id: int) -> None:
    """Admin only, and only once the project is completed."""
    project = ProjectRepository(db).find_by_id(project_id)
    if project is None:
        raise NotFound("Project not found")
    if project["archived_at"]:
        raise Conflict("This project is already archived")
    if not project["completed_at"]:
        raise Conflict("Only completed projects can be archived. Complete all milestones first.")
    ProjectRepository(db).archive(project_id)
    AuditRepository(db).add(actor, "archive", "project", project_id, f"Archived project {project['title']}")


def restore_project(db: Database, actor: User, project_id: int) -> dict:
    project = ProjectRepository(db).find_by_id(project_id)
    if project is None:
        raise NotFound("Project not found")
    if not project["archived_at"]:
        raise Conflict("This project isn't archived")
    manager = UserRepository(db).find_by_id(project["manager_id"])
    if manager["archived_at"]:
        raise Conflict("This project's manager is archived. Change the manager first, then restore it.")
    ProjectRepository(db).restore(project_id)
    AuditRepository(db).add(actor, "restore", "project", project_id, f"Restored project {project['title']}")
    return _detail(db, actor, project_id)


def change_manager(db: Database, actor: User, project_id: int, body: ManagerChange) -> dict:
    project = ProjectRepository(db).find_by_id(project_id)
    if project is None:
        raise NotFound("Project not found")
    _check_manager(db, body.manager_id)
    ProjectRepository(db).set_manager(project_id, body.manager_id)
    AuditRepository(db).add(actor, "update", "project", project_id, f"Changed the manager of {project['title']}",
                            {"manager_id": project["manager_id"]}, {"manager_id": body.manager_id})
    return _detail(db, actor, project_id)


def budget_history(db: Database, viewer: User, project_id: int) -> list[dict]:
    project_for(db, viewer, project_id)
    rows = ProjectRepository(db).budget_history(project_id)
    for row in rows:
        row["change"] = row["new_budget"] - row["old_budget"]
    return rows
