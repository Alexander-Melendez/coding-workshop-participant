"""People: admins manage everyone, managers manage their own team.

Every user has a users row. Employees also have an employees row holding
their title, salary and manager.
"""

from datetime import date

import config
import security
from db import Database
from errors import BadRequest, Conflict, Forbidden, NotFound
from models.entities import User, display_id, hourly_rate
from models.schemas import UserCreate, UserUpdate
from repositories.audit_repository import AuditRepository
from repositories.milestone_repository import MilestoneRepository
from repositories.user_repository import UserRepository
from services.common import week_of


def serialize_user(row: dict, viewer: User, with_workload: bool = False, db: Database | None = None,
                   workload: dict | None = None) -> dict:
    """User for the API. Salary only for people the viewer may see it for."""
    data = {
        "id": row["id"],
        "display_id": display_id(row["role"], row["id"]),
        "role": row["role"],
        "name": row["name"],
        "username": row["username"],
        "email": row["email"],
        "title": row["title"],
        "manager_id": row["manager_id"],
        "manager_name": row["manager_name"],
        "archived": row["archived_at"] is not None,
        "archived_at": row["archived_at"],
        "created_at": row["created_at"],
    }
    if row["role"] == "employee" and viewer.can_view_salary(row):
        data["salary"] = row["salary"]
        data["hourly_rate"] = hourly_rate(row["salary"])
    if with_workload and row["employee_id"]:
        if workload is None:
            workload = workloads(db, [row["employee_id"]])
        hours, current = workload.get(row["employee_id"], (0, None))
        data["hours_this_week"] = hours
        data["utilization_pct"] = round(float(hours) / config.HOURS_PER_WEEK * 100)
        data["current_assignment"] = current
    return data


def workloads(db: Database, employee_ids: list[int]) -> dict:
    """{employees.id: (hours logged this week, current assignment or None)}."""
    users = UserRepository(db)
    monday, sunday = week_of(date.today())
    hours = users.hours_between(employee_ids, monday, sunday)
    current = users.current_assignments(employee_ids)
    return {eid: (hours.get(eid, 0), current.get(eid)) for eid in employee_ids}


def serialize_many(db: Database, rows: list[dict], viewer: User) -> list[dict]:
    load = workloads(db, [r["employee_id"] for r in rows if r["employee_id"]])
    return [serialize_user(r, viewer, with_workload=True, db=db, workload=load) for r in rows]


def ensure_unique(users: UserRepository, username: str | None, email: str | None, except_id: int = 0) -> None:
    fields = {}
    if username and users.username_taken(username, except_id):
        fields["username"] = "This username is already taken"
    if email and users.email_taken(email, except_id):
        fields["email"] = "This email is already in use"
    if fields:
        raise Conflict("Username or email already in use", fields)


def _check_manager(users: UserRepository, manager_id: int | None) -> None:
    if manager_id is None:
        return
    manager = users.find_by_id(manager_id)
    if manager is None or manager["role"] != "manager" or manager["archived_at"]:
        raise BadRequest("Choose an active manager", {"manager_id": "Must be an active manager"})


def _load(users: UserRepository, user_id: int) -> dict:
    row = users.find_by_id(user_id)
    if row is None:
        raise NotFound("User not found")
    return row


# ---------------------------------------------------------------------------
def list_users(db: Database, viewer: User, search: str | None, role: str | None, status: str,
               manager_id: int | None) -> list[dict]:
    """Admins: everyone (filterable). Managers: only their own active employees."""
    users = UserRepository(db)
    archived = {"active": False, "archived": True, "all": None}.get(status, False)
    if not viewer.can_see_archived:
        archived = False
    if viewer.role == "manager":
        role, manager_id = "employee", viewer.id
    return serialize_many(db, users.search(archived=archived, role=role, manager_id=manager_id, text=search), viewer)


def create_user(db: Database, actor: User, body: UserCreate) -> dict:
    """Admin creates a user and gets a random 6-character password to hand over once."""
    users = UserRepository(db)
    if body.role != "employee" and body.manager_id:
        raise BadRequest("Only employees report to a manager", {"manager_id": "Only for employees"})
    _check_manager(users, body.manager_id)
    ensure_unique(users, body.username, body.email)

    password = security.generate_password(6)
    user_id = users.create(body.email, body.username, body.name, security.hash_password(password), body.role)
    if body.role == "employee":
        users.create_employee(user_id, body.title, body.salary, body.manager_id)
    row = users.find_by_id(user_id)
    AuditRepository(db).add(actor, "create", "user", user_id, f"Created {body.role} {body.name}", after=row)
    return {"user": serialize_user(row, actor), "temporary_password": password}


def get_user(db: Database, viewer: User, user_id: int) -> dict:
    row = _load(UserRepository(db), user_id)
    if row["archived_at"] and not viewer.can_see_archived:
        raise NotFound("User not found")
    if not viewer.can_view_user(row):
        raise Forbidden("You can only view people on your own team")
    return serialize_user(row, viewer, with_workload=True, db=db)


def update_user(db: Database, actor: User, user_id: int, body: UserUpdate) -> dict:
    """Change the fields this actor is allowed to change (see entities.editable_fields)."""
    users = UserRepository(db)
    before = _load(users, user_id)
    if before["archived_at"]:
        raise Conflict("Restore this person before editing them")
    allowed = actor.editable_fields(before)
    if not allowed:
        raise Forbidden("You can only edit people on your own team")
    sent = body.model_fields_set
    not_allowed = sent - allowed
    if not_allowed:
        raise Forbidden(f"You are not allowed to change: {', '.join(sorted(not_allowed))}")

    new = {**before, **body.model_dump(include=sent)}
    blank = [f for f in ("name", "email", "username", "role", "salary") if f in sent and new[f] is None]
    if blank:
        raise BadRequest("These fields can't be empty", {f: "This field is required" for f in blank})
    if new["role"] != before["role"]:
        _check_role_change(db, users, before, new["role"])
    if new["role"] != "employee" and "manager_id" in sent and new["manager_id"]:
        raise BadRequest("Only employees report to a manager", {"manager_id": "Only for employees"})
    if "manager_id" in sent and new["manager_id"] == user_id:
        raise BadRequest("Nobody can be their own manager", {"manager_id": "Choose someone else"})
    if "manager_id" in sent:
        _check_manager(users, new["manager_id"])
    ensure_unique(users, body.username, body.email, user_id)

    users.update_user(user_id, new["name"], new["email"], new["username"], new["role"])
    if new["role"] == "employee":
        if before["employee_id"]:
            users.update_employee(user_id, new["title"], new["salary"], new["manager_id"])
        else:
            users.create_employee(user_id, new["title"], new["salary"] or 0, new["manager_id"])
    after = users.find_by_id(user_id)
    AuditRepository(db).add(actor, "update", "user", user_id, f"Updated {after['name']}", before, after)
    return serialize_user(after, actor, with_workload=True, db=db)


def _check_role_change(db: Database, users: UserRepository, before: dict, new_role: str) -> None:
    """A manager with a team or projects, or an employee with work history, can't just change role."""
    if before["role"] == "manager":
        if users.has_active_team(before["id"]):
            raise Conflict("Move this manager's employees to another manager first")
        if db.one("SELECT id FROM projects WHERE manager_id = %s LIMIT 1", (before["id"],)):
            raise Conflict("Give this manager's projects to another manager first")
    if before["role"] == "employee":
        has_work = db.one(
            "SELECT id FROM milestone_assignments WHERE employee_id = %s "
            "UNION ALL SELECT id FROM time_entries WHERE employee_id = %s LIMIT 1",
            (before["employee_id"], before["employee_id"]),
        )
        if has_work:
            raise Conflict("This employee has assignments or logged hours, so their role can't change")
        db.run("DELETE FROM employees WHERE id = %s", (before["employee_id"],))


def archive_user(db: Database, actor: User, user_id: int) -> None:
    """Archive instead of delete: they can't sign in, but their history stays."""
    users = UserRepository(db)
    target = _load(users, user_id)
    if target["id"] == actor.id:
        raise Conflict("You can't archive your own account")
    if target["archived_at"]:
        raise Conflict("This person is already archived")
    if target["role"] == "admin" and users.count_active_admins() <= 1:
        raise Conflict("At least one active admin is needed")
    if target["role"] == "manager":
        if users.has_active_team(user_id):
            raise Conflict("Move this manager's employees to another manager first")
        projects = db.all("SELECT title FROM projects WHERE manager_id = %s AND archived_at IS NULL", (user_id,))
        if projects:
            raise Conflict(f"Give '{projects[0]['title']}' to another manager first")
    if target["role"] == "employee":
        MilestoneRepository(db).end_assignments_today(employee_id=target["employee_id"])
    users.archive(user_id)
    AuditRepository(db).add(actor, "archive", "user", user_id, f"Archived {target['name']}", target,
                            users.find_by_id(user_id))


def restore_user(db: Database, actor: User, user_id: int) -> dict:
    users = UserRepository(db)
    target = _load(users, user_id)
    if not target["archived_at"]:
        raise Conflict("This person isn't archived")
    note = ""
    if target["manager_id"]:
        boss = users.find_by_id(target["manager_id"])
        if boss["archived_at"]:
            users.update_employee(user_id, target["title"], target["salary"], None)
            note = " (their manager is archived, so they now have no manager)"
    users.restore(user_id)
    AuditRepository(db).add(actor, "restore", "user", user_id, f"Restored {target['name']}{note}")
    return serialize_user(users.find_by_id(user_id), actor)


def reset_password(db: Database, actor: User, user_id: int) -> dict:
    users = UserRepository(db)
    target = _load(users, user_id)
    if target["archived_at"]:
        raise Conflict("Restore this person first")
    password = security.generate_password(6)
    users.set_password(user_id, security.hash_password(password))
    AuditRepository(db).add(actor, "reset_password", "user", user_id, f"Reset the password for {target['name']}")
    return {"temporary_password": password}
