"""PostgreSQL connection, transactions and first-time setup.

Like init_db() in the banking app, init_db() prepares the database on
startup: it runs schema.sql if the tables don't exist yet, creates the
first admin, and loads the secret used to sign login tokens.

Every API request runs inside `with transaction() as db:`. If anything
fails, the whole request is rolled back, so data is never half-saved.
"""

import logging
import secrets
import threading
from contextlib import contextmanager
from pathlib import Path

from psycopg import OperationalError, connect
from psycopg.rows import dict_row

import config
import security

logger = logging.getLogger(__name__)

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"

# One connection per Lambda container (like the template's postgres_service.py).
# FastAPI runs routes on worker threads, so a lock makes sure only one
# transaction uses the connection at a time.
_connection = None
_lock = threading.RLock()
_ready = False


class Database:
    """Small helper around a connection. Rows come back as dicts."""

    def __init__(self, connection):
        self.connection = connection

    def all(self, sql: str, params=None) -> list[dict]:
        """Every row of a query."""
        with self.connection.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def one(self, sql: str, params=None) -> dict | None:
        """First row of a query, or None."""
        with self.connection.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def value(self, sql: str, params=None):
        """First column of the first row, or None."""
        row = self.one(sql, params)
        return next(iter(row.values())) if row else None

    def run(self, sql: str, params=None) -> int:
        """Run an INSERT/UPDATE/DELETE and return how many rows it changed."""
        with self.connection.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount


def _get_connection():
    global _connection
    if _connection is None or _connection.closed or _connection.broken:
        _connection = connect(config.postgres_conninfo(), row_factory=dict_row)
    return _connection


def reset_connection() -> None:
    """Forget the connection so the next request reconnects."""
    global _connection
    conn, _connection = _connection, None
    if conn is not None:
        try:
            conn.close()
        except Exception:  # noqa: BLE001 - closing a broken connection can fail; that's fine
            logger.debug("Ignoring error while closing a broken connection")


@contextmanager
def transaction():
    """Run a block in one transaction: commit on success, roll back on any error."""
    with _lock:
        init_db()
        conn = _get_connection()
        try:
            yield Database(conn)
            conn.commit()
        except OperationalError:
            reset_connection()
            raise
        except Exception:
            conn.rollback()
            raise


def init_db() -> None:
    """Create the tables (first run only), the first admin and the token secret."""
    global _ready
    if _ready:
        return
    conn = _get_connection()
    db = Database(conn)
    try:
        # Lock so two Lambdas starting at the same time don't both create tables
        db.value("SELECT pg_advisory_xact_lock(727274)")
        if db.value("SELECT to_regclass('public.users')") is None:
            logger.info("Creating tables from schema.sql")
            db.run(SCHEMA_FILE.read_text(encoding="utf-8"))
        _create_first_admin(db)
        db.run(
            "INSERT INTO app_settings (key, value) VALUES ('jwt_secret', %s) ON CONFLICT (key) DO NOTHING",
            (secrets.token_urlsafe(48),),
        )
        security.set_secret(db.value("SELECT value FROM app_settings WHERE key = 'jwt_secret'"))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    _ready = True


def _create_first_admin(db: Database) -> None:
    """Only admins can create users, so without this nobody could ever sign in."""
    if db.value("SELECT id FROM users WHERE role = 'admin' LIMIT 1"):
        return
    admin_id = db.value(
        """
        INSERT INTO users (email, username, name, password_hash, role)
        VALUES (%s, %s, 'System Administrator', %s, 'admin')
        RETURNING id
        """,
        (config.SEED_ADMIN_EMAIL, config.SEED_ADMIN_USERNAME, security.hash_password(config.SEED_ADMIN_PASSWORD)),
    )
    db.run(
        "INSERT INTO audit_log (action, entity_type, entity_id, summary) "
        "VALUES ('seed', 'user', %s, 'Created the first admin account')",
        (admin_id,),
    )
