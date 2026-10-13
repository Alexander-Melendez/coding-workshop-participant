"""Time entries, the dashboard, and the audit log."""

from datetime import date

from fastapi import APIRouter, Depends, Response

from auth import get_current_user, require_roles
from db import transaction
from models.entities import User
from models.schemas import TimeEntryCreate, TimeEntryUpdate
from services import audit_service, dashboard_service, time_service

router = APIRouter(tags=["Time, dashboard and audit"])

employees_only = require_roles(["employee"])
admin_only = require_roles(["admin"])


@router.get("/time-entries")
def list_entries(project_id: int | None = None, user_id: int | None = None,
                 date_from: date | None = None, date_to: date | None = None,
                 user: User = Depends(get_current_user)):
    with transaction() as db:
        return time_service.list_entries(db, user, project_id, user_id, date_from, date_to)


@router.post("/time-entries", status_code=201)
def create_entry(body: TimeEntryCreate, user: User = Depends(employees_only)):
    with transaction() as db:
        return time_service.create_entry(db, user, body)


@router.put("/time-entries/{entry_id}")
def update_entry(entry_id: int, body: TimeEntryUpdate, user: User = Depends(employees_only)):
    with transaction() as db:
        return time_service.update_entry(db, user, entry_id, body)


@router.delete("/time-entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int, user: User = Depends(get_current_user)):
    """Your own entries (admins may delete any)."""
    with transaction() as db:
        time_service.delete_entry(db, user, entry_id)
    return Response(status_code=204)


@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user)):
    """Everything the signed-in role's home page needs, in one call."""
    with transaction() as db:
        return dashboard_service.dashboard(db, user)


@router.get("/audit-logs")
def audit_logs(action: str | None = None, entity_type: str | None = None, search: str | None = None,
               date_from: date | None = None, date_to: date | None = None,
               limit: int = 50, offset: int = 0, user: User = Depends(admin_only)):
    with transaction() as db:
        return audit_service.list_audit_log(db, action, entity_type, search, date_from, date_to, limit, offset)
