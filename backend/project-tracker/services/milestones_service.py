"""Milestones and who is assigned to them.

Rules:
- milestone dates sit inside the project's dates
- assignment dates sit inside the milestone's dates
- an employee works full-time on ONE milestone at a time (no overlapping assignments)
- managers assign only their own employees; admins can assign anyone
- a completed milestone (completed_at set) is locked
- completing a milestone frees its people from tomorrow
"""

from datetime import date

from db import Database
from errors import BadRequest, Conflict, Forbidden, NotFound
from models.entities import User
from models.schemas import AssignmentCreate, AssignmentUpdate, MilestoneCreate, MilestoneUpdate
from repositories.audit_repository import AuditRepository
from repositories.milestone_repository import MilestoneRepository
from repositories.user_repository import UserRepository
from services.common import (
    check_date_order,
    ensure_milestone_open,
    ensure_project_open,
    milestone_for,
    milestone_status,
    number,
    project_for,
)


def serialize_milestone(db: Database, milestone: dict, viewer: User) -> dict:
    repo = MilestoneRepository(db)
    totals = repo.hours_and_cost(milestone["id"])
    status = milestone_status(milestone)
    data = {
        "id": milestone["id"],
        "project_id": milestone["project_id"],
        "title": milestone["title"],
        "description": milestone["description"],
        "start_date": milestone["start_date"],
        "end_date": milestone["end_date"],
        "completed_at": milestone["completed_at"],
        "status": status,
        "locked": status == "complete",
        "overdue": status != "complete" and milestone["end_date"] < date.today(),
        "hours_logged": number(totals["hours"]),
        "assignments": [serialize_assignment(a) for a in repo.assignments_for(milestone["id"])],
    }
    if viewer.can_see_costs:
        data["cost"] = number(totals["cost"])
    return data


def serialize_assignment(row: dict) -> dict:
    return {
        "id": row["id"],
        "milestone_id": row["milestone_id"],
        "milestone_title": row["milestone_title"],
        "milestone_completed": row["milestone_completed_at"] is not None,
        "project_id": row["project_id"],
        "project_title": row["project_title"],
        "user_id": row["user_id"],
        "employee_name": row["employee_name"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
    }


def _inside(field_start: str, field_end: str, start, end, outer_start, outer_end, what: str) -> None:
    fields = {}
    if start < outer_start:
        fields[field_start] = f"Must be on or after the {what} start ({outer_start})"
    if end > outer_end:
        fields[field_end] = f"Must be on or before the {what} end ({outer_end})"
    if fields:
        raise BadRequest(f"Dates must fall inside the {what} dates", fields)


# --- milestones -------------------------------------------------------------
def list_milestones(db: Database, viewer: User, project_id: int) -> list[dict]:
    project_for(db, viewer, project_id)
    return [serialize_milestone(db, m, viewer) for m in MilestoneRepository(db).for_project(project_id)]


def create_milestone(db: Database, actor: User, project_id: int, body: MilestoneCreate) -> dict:
    project = project_for(db, actor, project_id, manage=True)
    ensure_project_open(project)
    check_date_order(body.start_date, body.end_date)
    _inside("start_date", "end_date", body.start_date, body.end_date,
            project["start_date"], project["end_date"], "project")
    repo = MilestoneRepository(db)
    milestone_id = repo.create(project_id, body.title, body.description, body.start_date, body.end_date)
    milestone = repo.find_by_id(milestone_id)
    AuditRepository(db).add(actor, "create", "milestone", milestone_id,
                            f"Added milestone '{body.title}' to {project['title']}", after=milestone)
    return serialize_milestone(db, milestone, actor)


def get_milestone(db: Database, viewer: User, milestone_id: int) -> dict:
    milestone, _ = milestone_for(db, viewer, milestone_id)
    return serialize_milestone(db, milestone, viewer)


def update_milestone(db: Database, actor: User, milestone_id: int, body: MilestoneUpdate) -> dict:
    """While a milestone is open its dates can move; once complete it's locked."""
    milestone, project = milestone_for(db, actor, milestone_id, manage=True)
    ensure_project_open(project)
    ensure_milestone_open(milestone)
    sent = body.model_dump(include=body.model_fields_set)
    if "title" in sent and not sent["title"]:
        raise BadRequest("The title can't be empty", {"title": "This field is required"})
    new = {**milestone, **{k: v for k, v in sent.items() if v is not None or k == "description"}}
    check_date_order(new["start_date"], new["end_date"])
    _inside("start_date", "end_date", new["start_date"], new["end_date"],
            project["start_date"], project["end_date"], "project")

    repo = MilestoneRepository(db)
    clash = repo.assignment_outside(milestone_id, new["start_date"], new["end_date"])
    if clash:
        raise BadRequest(f"{clash['employee_name']}'s assignment falls outside these dates. Change it first.",
                         {"start_date": "Must include every assignment", "end_date": "Must include every assignment"})
    if repo.time_outside(milestone_id, new["start_date"], new["end_date"]):
        raise BadRequest("Hours were already logged outside these dates",
                         {"start_date": "Must include all logged hours", "end_date": "Must include all logged hours"})

    repo.update(milestone_id, new["title"], new["description"], new["start_date"], new["end_date"])
    after = repo.find_by_id(milestone_id)
    AuditRepository(db).add(actor, "update", "milestone", milestone_id, f"Updated milestone '{after['title']}'",
                            milestone, after)
    return serialize_milestone(db, after, actor)


def complete_milestone(db: Database, actor: User, milestone_id: int) -> dict:
    milestone, project = milestone_for(db, actor, milestone_id, manage=True)
    ensure_project_open(project)
    ensure_milestone_open(milestone)
    repo = MilestoneRepository(db)
    repo.mark_completed(milestone_id)
    repo.end_assignments_today(milestone_id=milestone_id)
    AuditRepository(db).add(actor, "complete", "milestone", milestone_id, f"Completed milestone '{milestone['title']}'")
    return serialize_milestone(db, repo.find_by_id(milestone_id), actor)


def delete_milestone(db: Database, actor: User, milestone_id: int) -> None:
    """Only for milestones with no logged hours (e.g. created by mistake)."""
    milestone, project = milestone_for(db, actor, milestone_id, manage=True)
    ensure_project_open(project)
    ensure_milestone_open(milestone)
    repo = MilestoneRepository(db)
    if repo.has_time(milestone_id):
        raise Conflict("Hours have been logged on this milestone, so it can't be deleted")
    repo.delete(milestone_id)
    AuditRepository(db).add(actor, "delete", "milestone", milestone_id,
                            f"Deleted milestone '{milestone['title']}' from {project['title']}", before=milestone)


# --- assignments ------------------------------------------------------------
def _check_overlap(repo: MilestoneRepository, employee_id: int, start, end, except_id: int = 0) -> None:
    clash = repo.overlapping_assignment(employee_id, start, end, except_id)
    if clash:
        raise Conflict(
            f"{clash['employee_name']} is already on '{clash['milestone_title']}' ({clash['project_title']}) "
            f"from {clash['start_date']} to {clash['end_date']}. Employees work on one milestone at a time."
        )


def list_assignments_for(db: Database, viewer: User, milestone_id: int) -> list[dict]:
    milestone_for(db, viewer, milestone_id)
    return [serialize_assignment(a) for a in MilestoneRepository(db).assignments_for(milestone_id)]


def list_assignments(db: Database, viewer: User, current_only: bool) -> list[dict]:
    """Employees: their own. Managers: their projects and their team. Admins: all."""
    where, params = ["p.archived_at IS NULL"], []
    if viewer.role == "employee":
        where.append("a.employee_id = %s")
        params.append(viewer.employee_id)
    elif viewer.role == "manager":
        where.append("(e.manager_id = %s OR p.manager_id = %s)")
        params += [viewer.id, viewer.id]
    if current_only:
        where.append("a.end_date >= CURRENT_DATE")
    return [serialize_assignment(a) for a in MilestoneRepository(db).search_assignments(where, params)]


def create_assignment(db: Database, actor: User, milestone_id: int, body: AssignmentCreate) -> dict:
    milestone, project = milestone_for(db, actor, milestone_id, manage=True)
    ensure_project_open(project)
    ensure_milestone_open(milestone)
    check_date_order(body.start_date, body.end_date)
    _inside("start_date", "end_date", body.start_date, body.end_date,
            milestone["start_date"], milestone["end_date"], "milestone")

    employee = UserRepository(db).find_by_id(body.user_id)
    if employee is None or employee["role"] != "employee" or employee["archived_at"]:
        raise BadRequest("Choose an active employee", {"user_id": "Must be an active employee"})
    if not actor.can_assign(employee):
        raise Forbidden("Managers can only assign employees from their own team")

    repo = MilestoneRepository(db)
    _check_overlap(repo, employee["employee_id"], body.start_date, body.end_date)
    assignment_id = repo.create_assignment(milestone_id, employee["employee_id"], body.start_date, body.end_date)
    AuditRepository(db).add(actor, "assign", "assignment", assignment_id,
                            f"Assigned {employee['name']} to '{milestone['title']}' "
                            f"({body.start_date} to {body.end_date})")
    return serialize_assignment(repo.assignment(assignment_id))


def _assignment_for(db: Database, actor: User, assignment_id: int) -> tuple[dict, dict]:
    assignment = MilestoneRepository(db).assignment(assignment_id)
    if assignment is None:
        raise NotFound("Assignment not found")
    milestone, project = milestone_for(db, actor, assignment["milestone_id"], manage=True)
    ensure_project_open(project)
    ensure_milestone_open(milestone)
    return assignment, milestone


def update_assignment(db: Database, actor: User, assignment_id: int, body: AssignmentUpdate) -> dict:
    assignment, milestone = _assignment_for(db, actor, assignment_id)
    start = body.start_date or assignment["start_date"]
    end = body.end_date or assignment["end_date"]
    check_date_order(start, end)
    _inside("start_date", "end_date", start, end, milestone["start_date"], milestone["end_date"], "milestone")
    repo = MilestoneRepository(db)
    _check_overlap(repo, assignment["employee_id"], start, end, except_id=assignment_id)
    repo.update_assignment(assignment_id, start, end)
    AuditRepository(db).add(actor, "update", "assignment", assignment_id,
                            f"Moved {assignment['employee_name']}'s dates on '{milestone['title']}'",
                            {"start_date": assignment["start_date"], "end_date": assignment["end_date"]},
                            {"start_date": start, "end_date": end})
    return serialize_assignment(repo.assignment(assignment_id))


def delete_assignment(db: Database, actor: User, assignment_id: int) -> None:
    """Take someone off a milestone. Hours they already logged are kept."""
    assignment, milestone = _assignment_for(db, actor, assignment_id)
    MilestoneRepository(db).delete_assignment(assignment_id)
    AuditRepository(db).add(actor, "unassign", "assignment", assignment_id,
                            f"Removed {assignment['employee_name']} from '{milestone['title']}'")
