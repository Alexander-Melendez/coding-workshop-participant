"""Milestones and assignments (who works on which milestone, when)."""

from fastapi import APIRouter, Depends, Response

from auth import get_current_user, require_roles
from db import transaction
from models.entities import User
from models.schemas import AssignmentCreate, AssignmentUpdate, MilestoneUpdate
from services import milestones_service

router = APIRouter(tags=["Milestones"])

staff = require_roles(["admin", "manager"])


@router.get("/milestones/{milestone_id}")
def get_milestone(milestone_id: int, user: User = Depends(get_current_user)):
    with transaction() as db:
        return milestones_service.get_milestone(db, user, milestone_id)


@router.put("/milestones/{milestone_id}")
def update_milestone(milestone_id: int, body: MilestoneUpdate, user: User = Depends(staff)):
    with transaction() as db:
        return milestones_service.update_milestone(db, user, milestone_id, body)


@router.post("/milestones/{milestone_id}/complete")
def complete_milestone(milestone_id: int, user: User = Depends(staff)):
    """Locks the milestone and frees its people from tomorrow."""
    with transaction() as db:
        return milestones_service.complete_milestone(db, user, milestone_id)


@router.delete("/milestones/{milestone_id}", status_code=204)
def delete_milestone(milestone_id: int, user: User = Depends(staff)):
    with transaction() as db:
        milestones_service.delete_milestone(db, user, milestone_id)
    return Response(status_code=204)


@router.get("/milestones/{milestone_id}/assignments")
def list_assignments_for(milestone_id: int, user: User = Depends(get_current_user)):
    with transaction() as db:
        return milestones_service.list_assignments_for(db, user, milestone_id)


@router.post("/milestones/{milestone_id}/assignments", status_code=201)
def create_assignment(milestone_id: int, body: AssignmentCreate, user: User = Depends(staff)):
    with transaction() as db:
        return milestones_service.create_assignment(db, user, milestone_id, body)


@router.get("/assignments")
def list_assignments(current: bool = False, user: User = Depends(get_current_user)):
    """Employees see their own; managers their projects and team; admins all."""
    with transaction() as db:
        return milestones_service.list_assignments(db, user, current)


@router.put("/assignments/{assignment_id}")
def update_assignment(assignment_id: int, body: AssignmentUpdate, user: User = Depends(staff)):
    with transaction() as db:
        return milestones_service.update_assignment(db, user, assignment_id, body)


@router.delete("/assignments/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: int, user: User = Depends(staff)):
    with transaction() as db:
        milestones_service.delete_assignment(db, user, assignment_id)
    return Response(status_code=204)
