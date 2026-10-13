"""Projects, their milestones list and budget history."""

from typing import Literal

from fastapi import APIRouter, Depends, Response

from auth import get_current_user, require_roles
from db import transaction
from models.entities import User
from models.schemas import ManagerChange, MilestoneCreate, ProjectCreate, ProjectUpdate
from services import milestones_service, projects_service

router = APIRouter(prefix="/projects", tags=["Projects"])

admin_only = require_roles(["admin"])
staff = require_roles(["admin", "manager"])


@router.get("")
def list_projects(search: str | None = None,
                  status: Literal["active", "completed", "archived", "all"] | None = None,
                  health: Literal["white", "red", "green"] | None = None,
                  at_risk: bool = False,
                  user: User = Depends(get_current_user)):
    """Projects this user can see. Default: everything not archived."""
    with transaction() as db:
        return projects_service.list_projects(db, user, search, status, health, at_risk)


@router.post("", status_code=201)
def create_project(body: ProjectCreate, user: User = Depends(admin_only)):
    with transaction() as db:
        return projects_service.create_project(db, user, body)


@router.get("/{project_id}")
def get_project(project_id: int, user: User = Depends(get_current_user)):
    with transaction() as db:
        return projects_service.get_project(db, user, project_id)


@router.put("/{project_id}")
def update_project(project_id: int, body: ProjectUpdate, user: User = Depends(staff)):
    with transaction() as db:
        return projects_service.update_project(db, user, project_id, body)


@router.delete("/{project_id}", status_code=204)
def archive_project(project_id: int, user: User = Depends(admin_only)):
    """Archive (projects are never deleted). Only completed projects."""
    with transaction() as db:
        projects_service.archive_project(db, user, project_id)
    return Response(status_code=204)


@router.post("/{project_id}/complete")
def complete_project(project_id: int, user: User = Depends(staff)):
    with transaction() as db:
        return projects_service.complete_project(db, user, project_id)


@router.post("/{project_id}/restore")
def restore_project(project_id: int, user: User = Depends(admin_only)):
    with transaction() as db:
        return projects_service.restore_project(db, user, project_id)


@router.put("/{project_id}/manager")
def change_manager(project_id: int, body: ManagerChange, user: User = Depends(admin_only)):
    with transaction() as db:
        return projects_service.change_manager(db, user, project_id, body)


@router.get("/{project_id}/budget-history")
def budget_history(project_id: int, user: User = Depends(staff)):
    with transaction() as db:
        return projects_service.budget_history(db, user, project_id)


@router.get("/{project_id}/milestones")
def list_milestones(project_id: int, user: User = Depends(get_current_user)):
    with transaction() as db:
        return milestones_service.list_milestones(db, user, project_id)


@router.post("/{project_id}/milestones", status_code=201)
def create_milestone(project_id: int, body: MilestoneCreate, user: User = Depends(staff)):
    with transaction() as db:
        return milestones_service.create_milestone(db, user, project_id, body)
