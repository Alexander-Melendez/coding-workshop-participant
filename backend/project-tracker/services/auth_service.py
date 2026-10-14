"""Sign in, refresh tokens, and the signed-in user's own profile."""

import security
from db import Database
from errors import BadRequest, Unauthorized
from models.entities import User, user_from_row
from models.schemas import PasswordChange, ProfileUpdate
from repositories.audit_repository import AuditRepository
from repositories.user_repository import UserRepository
from services.users_service import ensure_unique_email, serialize_user


def _tokens(row: dict) -> dict:
    user = user_from_row(row)
    access, expires_in = security.create_token(user.id, user.role, "access")
    refresh, _ = security.create_token(user.id, user.role, "refresh")
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer",
            "expires_in": expires_in, "user": serialize_user(row, user)}


def login(db: Database, username: str, password: str) -> dict:
    """Username or email + password -> tokens. Failed attempts are audited."""
    row = UserRepository(db).find_by_login(username)
    if row is None or row["archived_at"] or not verify(password, row):
        AuditRepository(db).add(None, "login_failed", "user", row["id"] if row else None,
                                f"Failed sign-in for '{username}'")
        db.connection.commit()  # keep the audit row even though the request fails
        raise Unauthorized("Incorrect username or password")
    user = user_from_row(row)
    AuditRepository(db).add(user, "login", "user", user.id, f"{user.name} signed in")
    return _tokens(row)


def logout(db: Database, user: User) -> None:
    """Record a sign-out. The browser then forgets its tokens.

    Tokens are stateless, so the access token stays valid until it expires
    (30 minutes); this entry records that the person chose to sign out.
    """
    AuditRepository(db).add(user, "logout", "user", user.id, f"{user.name} signed out")


def verify(password: str, row: dict) -> bool:
    return security.verify_password(password, row["password_hash"])


def refresh(db: Database, refresh_token: str) -> dict:
    """A valid refresh token -> new tokens."""
    payload = security.read_token(refresh_token, kind="refresh")
    row = UserRepository(db).find_by_id(int(payload["sub"]))
    if row is None or row["archived_at"]:
        raise Unauthorized("This account is no longer active")
    return _tokens(row)


def current_user(db: Database, access_token: str) -> User:
    """Turn an access token into the signed-in user (re-read from the database every time,
    so archiving someone or changing their role takes effect immediately)."""
    payload = security.read_token(access_token, kind="access")
    row = UserRepository(db).find_by_id(int(payload["sub"]))
    if row is None or row["archived_at"]:
        raise Unauthorized("This account is no longer active")
    return user_from_row(row)


def me(db: Database, user: User) -> dict:
    return serialize_user(UserRepository(db).find_by_id(user.id), user, with_workload=True, db=db)


def update_profile(db: Database, user: User, body: ProfileUpdate) -> dict:
    """Anyone can change their own name and email."""
    users = UserRepository(db)
    before = users.find_by_id(user.id)
    name = body.name or before["name"]
    email = body.email or before["email"]
    ensure_unique_email(users, email, user.id)
    users.update_user(user.id, name, email, before["role"])
    after = users.find_by_id(user.id)
    AuditRepository(db).add(user, "update", "user", user.id, "Updated own profile", before, after)
    return serialize_user(after, user)


def change_password(db: Database, user: User, body: PasswordChange) -> dict:
    if not security.verify_password(body.current_password, user.password_hash):
        raise BadRequest("Your current password is incorrect", {"current_password": "Incorrect password"})
    if body.current_password == body.new_password:
        raise BadRequest("Choose a different password", {"new_password": "Must be different from the current one"})
    UserRepository(db).set_password(user.id, security.hash_password(body.new_password))
    AuditRepository(db).add(user, "change_password", "user", user.id, "Changed own password")
    return {"message": "Password changed"}
