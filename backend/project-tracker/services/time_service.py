"""Time entries: hours employees log on the milestone they're assigned to.

Rules: at most 8 hours a day (one entry per day), at most 40 a week, not in
the future, only on dates the employee is assigned to that milestone, never
before the milestones it depends on are complete, and never on a completed
milestone or closed project. The hourly rate is saved
with each entry (salary / 2080), so a later raise doesn't change past costs.
"""

from datetime import date
from decimal import Decimal

import config
from db import Database
from errors import BadRequest, Conflict, Forbidden, NotFound
from models.entities import User, hourly_rate
from models.schemas import TimeEntryCreate, TimeEntryUpdate
from repositories.audit_repository import AuditRepository
from repositories.milestone_repository import MilestoneRepository
from repositories.time_entry_repository import TimeEntryRepository
from services.common import ensure_milestone_open, ensure_project_open, milestone_for, week_of


def serialize_entry(row: dict, viewer: User) -> dict:
    data = {
        "id": row["id"],
        "user_id": row["user_id"],
        "employee_name": row["employee_name"],
        "milestone_id": row["milestone_id"],
        "milestone_title": row["milestone_title"],
        "project_id": row["project_id"],
        "project_title": row["project_title"],
        "work_date": row["work_date"],
        "hours": row["hours"],
        "note": row["note"],
        "locked": row["milestone_completed_at"] is not None,
    }
    # Rate and cost reveal salary: only for the person, their manager and admins
    person = {"id": row["user_id"], "role": "employee", "manager_id": row["employee_manager_id"]}
    if viewer.can_view_salary(person):
        data["hourly_rate"] = row["hourly_rate"]
        data["cost"] = row["cost"]
    return data


def _check_rules(db: Database, employee_id: int, milestone_id: int, work_date: date, hours: Decimal,
                 except_id: int = 0) -> None:
    if work_date > date.today():
        raise BadRequest("You can't log time in the future", {"work_date": "Can't be in the future"})
    milestones = MilestoneRepository(db)
    waiting = [p["title"] for p in milestones.predecessors(milestone_id) if p["completed_at"] is None]
    if waiting:
        names = ", ".join(f"'{title}'" for title in waiting)
        raise BadRequest(f"This milestone can't start until {names} is complete",
                         {"milestone_id": "Waiting on an earlier milestone"})
    if not milestones.is_assigned_on(employee_id, milestone_id, work_date):
        raise BadRequest("You aren't assigned to this milestone on that date",
                         {"work_date": "You aren't assigned to this milestone on that date"})
    entries = TimeEntryRepository(db)
    if entries.logged_on(employee_id, work_date, except_id):
        raise Conflict(f"You already logged time on {work_date}. Edit that entry instead.",
                       {"work_date": "Already logged"})
    monday, sunday = week_of(work_date)
    week_total = Decimal(entries.hours_between(employee_id, monday, sunday, except_id))
    if week_total + hours > config.HOURS_PER_WEEK:
        left = config.HOURS_PER_WEEK - week_total
        raise BadRequest(f"That would make {week_total + hours} hours in the week of {monday} "
                         f"(limit {config.HOURS_PER_WEEK}).", {"hours": f"Only {left} hours left that week"})


# ---------------------------------------------------------------------------
def list_entries(db: Database, viewer: User, project_id: int | None, user_id: int | None,
                 date_from: date | None, date_to: date | None) -> list[dict]:
    """Employees: their own. Managers: their projects and their team. Admins: all."""
    where, params = [], []
    if viewer.role == "employee":
        where.append("t.employee_id = %s")
        params.append(viewer.employee_id)
    elif viewer.role == "manager":
        where.append("(e.manager_id = %s OR p.manager_id = %s)")
        params += [viewer.id, viewer.id]
    if not viewer.can_see_archived:
        where.append("p.archived_at IS NULL")
    if project_id:
        where.append("p.id = %s")
        params.append(project_id)
    if user_id:
        where.append("u.id = %s")
        params.append(user_id)
    if date_from:
        where.append("t.work_date >= %s")
        params.append(date_from)
    if date_to:
        where.append("t.work_date <= %s")
        params.append(date_to)
    return [serialize_entry(r, viewer) for r in TimeEntryRepository(db).search(where, params)]


def create_entry(db: Database, employee: User, body: TimeEntryCreate) -> dict:
    milestone, project = milestone_for(db, employee, body.milestone_id)
    ensure_project_open(project)
    ensure_milestone_open(milestone)
    _check_rules(db, employee.employee_id, body.milestone_id, body.work_date, body.hours)
    entries = TimeEntryRepository(db)
    entry_id = entries.create(employee.employee_id, body.milestone_id, body.work_date, body.hours,
                              hourly_rate(employee.salary), body.note)
    AuditRepository(db).add(employee, "create", "time_entry", entry_id,
                            f"Logged {body.hours}h on '{milestone['title']}' for {body.work_date}")
    return serialize_entry(entries.find_by_id(entry_id), employee)


def _own_entry(db: Database, user: User, entry_id: int) -> tuple[dict, dict]:
    entry = TimeEntryRepository(db).find_by_id(entry_id)
    if entry is None:
        raise NotFound("Time entry not found")
    if entry["employee_id"] != user.employee_id and user.role != "admin":
        raise Forbidden("You can only change your own time entries")
    milestone, project = milestone_for(db, user, entry["milestone_id"])
    ensure_project_open(project)
    ensure_milestone_open(milestone)
    return entry, milestone


def update_entry(db: Database, employee: User, entry_id: int, body: TimeEntryUpdate) -> dict:
    entry, milestone = _own_entry(db, employee, entry_id)
    work_date = body.work_date or entry["work_date"]
    hours = body.hours or entry["hours"]
    note = body.note if "note" in body.model_fields_set else entry["note"]
    _check_rules(db, entry["employee_id"], entry["milestone_id"], work_date, Decimal(hours), except_id=entry_id)
    entries = TimeEntryRepository(db)
    entries.update(entry_id, work_date, hours, note)
    AuditRepository(db).add(employee, "update", "time_entry", entry_id,
                            f"Edited time on '{milestone['title']}' for {work_date}",
                            {"work_date": entry["work_date"], "hours": entry["hours"], "note": entry["note"]},
                            {"work_date": work_date, "hours": hours, "note": note})
    return serialize_entry(entries.find_by_id(entry_id), employee)


def delete_entry(db: Database, user: User, entry_id: int) -> None:
    entry, milestone = _own_entry(db, user, entry_id)
    TimeEntryRepository(db).delete(entry_id)
    AuditRepository(db).add(user, "delete", "time_entry", entry_id,
                            f"Deleted {entry['hours']}h on '{milestone['title']}' for {entry['work_date']}")
