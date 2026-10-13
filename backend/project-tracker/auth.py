"""FastAPI dependencies for authentication and role checks.

Same pattern as the banking app:

    @router.get("/audit-logs")
    def audit(user: User = Depends(require_roles(["admin"]))): ...

Authentication first (a valid, unexpired token from an active user), then
authorization (the user's role is allowed). Finer checks, like "is this
your project?", are made in the services by asking the User object.
"""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from db import transaction
from errors import Forbidden, Unauthorized
from models.entities import User
from services import auth_service

# auto_error=False so a missing token gives our own 401 message, not FastAPI's default 403
bearer = HTTPBearer(auto_error=False)


def get_current_user(request: Request,
                     credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> User:
    """The signed-in user, as an Admin, Manager or Employee object."""
    # X-Auth-Token is a fallback for proxies that drop the Authorization header
    token = credentials.credentials if credentials else request.headers.get("x-auth-token")
    if not token:
        raise Unauthorized("Please sign in")
    with transaction() as db:
        return auth_service.current_user(db, token)


def require_roles(allowed_roles: list[str]):
    """Dependency factory: only let these roles through."""

    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise Forbidden(f"Your role ({user.role}) isn't allowed to do this")
        return user

    return role_checker
