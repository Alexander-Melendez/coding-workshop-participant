"""Password hashing and login tokens (JWT).

Passwords use PBKDF2-SHA256 from Python's standard library. Unlike argon2
or bcrypt it has no compiled code, so it can't break when the Lambda
package is built on a different operating system. The stored value keeps
the iteration count, so it can be raised later:

    pbkdf2_sha256$<iterations>$<salt>$<hash>
"""

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt

import config
from errors import Unauthorized

_secret = None


# --- passwords ----------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash a password with a random salt."""
    iterations = config.PASSWORD_HASH_ITERATIONS
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str | None) -> bool:
    """True if the password matches the stored hash."""
    try:
        name, iterations, salt, expected = (stored or "").split("$")
        if name != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(iterations))
        return hmac.compare_digest(digest, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False


def generate_password(length: int = 6) -> str:
    """Random temporary password with letters and at least one digit (no look-alikes like 0/O)."""
    letters = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "23456789"
    while True:
        password = "".join(secrets.choice(letters + digits) for _ in range(length))
        if any(c in digits for c in password) and any(c in letters for c in password):
            return password


# --- tokens -------------------------------------------------------------
def set_secret(secret: str) -> None:
    """Called by db.init_db() with the secret stored in app_settings."""
    global _secret
    _secret = secret


def create_token(user_id: int, role: str, kind: str = "access") -> tuple[str, int]:
    """Signed token for a user. Returns (token, seconds until it expires).

    kind="access" is sent with every request (short-lived);
    kind="refresh" is only used to get a new access token.
    """
    if kind == "access":
        lifetime = timedelta(minutes=config.ACCESS_TOKEN_MINUTES)
    else:
        lifetime = timedelta(hours=config.REFRESH_TOKEN_HOURS)
    now = datetime.now(UTC)
    payload = {"sub": str(user_id), "role": role, "kind": kind,
               "iat": now, "exp": now + lifetime, "jti": secrets.token_hex(8)}
    return jwt.encode(payload, _secret, algorithm="HS256"), int(lifetime.total_seconds())


def read_token(token: str, kind: str = "access") -> dict:
    """Check a token's signature, expiry and kind. Raises Unauthorized if bad."""
    try:
        payload = jwt.decode(token, _secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("Your session has expired. Please sign in again.") from exc
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid sign-in token") from exc
    if payload.get("kind") != kind:
        raise Unauthorized("Invalid sign-in token")
    return payload
