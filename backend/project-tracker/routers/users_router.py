"""People. Admins manage everyone; managers see and edit their own team."""

from typing import Literal

from fastapi import APIRouter, Depends, Response

from auth import require_roles
from db import transaction
from models.entities import User
from models.schemas import UserCreate, UserUpdate
from services import users_service

router = APIRouter(prefix="/users", tags=["Users"])

admin_only = require_roles(["admin"])
staff = require_roles(["admin", "manager"])
employee_only = require_roles(["employee"])


@router.get("")
def list_users(search: str | None = None, role: Literal["admin", "manager", "employee"] | None = None,
               status: Literal["active", "archived", "all"] = "active", manager_id: int | None = None,
               user: User = Depends(staff)):
    with transaction() as db:
        return users_service.list_users(db, user, search, role, status, manager_id)


@router.get("/my-team")
def my_team(user: User = Depends(employee_only)):
    """For employees: their manager and teammates (contact details only)."""
    with transaction() as db:
        return users_service.my_team(db, user)


@router.post("", status_code=201)
def create_user(body: UserCreate, user: User = Depends(admin_only)):
    """Returns the new user and a 6-character temporary password (shown once)."""
    with transaction() as db:
        return users_service.create_user(db, user, body)


@router.get("/{user_id}")
def get_user(user_id: int, user: User = Depends(staff)):
    with transaction() as db:
        return users_service.get_user(db, user, user_id)


@router.put("/{user_id}")
def update_user(user_id: int, body: UserUpdate, user: User = Depends(staff)):
    with transaction() as db:
        return users_service.update_user(db, user, user_id, body)


@router.delete("/{user_id}", status_code=204)
def archive_user(user_id: int, user: User = Depends(admin_only)):
    """Archive (users are never deleted)."""
    with transaction() as db:
        users_service.archive_user(db, user, user_id)
    return Response(status_code=204)


@router.post("/{user_id}/restore")
def restore_user(user_id: int, user: User = Depends(admin_only)):
    with transaction() as db:
        return users_service.restore_user(db, user, user_id)


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, user: User = Depends(admin_only)):
    with transaction() as db:
        return users_service.reset_password(db, user, user_id)
