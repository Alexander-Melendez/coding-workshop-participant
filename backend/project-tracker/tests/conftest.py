"""Shared test setup.

Tests use their own database, `tracker_test` (created automatically on the
same PostgreSQL server), so your development data is never touched.

    cd backend/project-tracker
    pip install -r requirements.txt -r requirements-dev.txt
    pytest
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_DIR))

TEST_DB = os.getenv("TEST_POSTGRES_NAME", "tracker_test")
os.environ["POSTGRES_NAME"] = TEST_DB
os.environ["PASSWORD_HASH_ITERATIONS"] = "1000"  # fast hashing, tests only

import config  # noqa: E402
import db as database  # noqa: E402
from errors import ApiError  # noqa: E402
from models.entities import user_from_row  # noqa: E402
from models.schemas import MilestoneCreate, ProjectCreate, UserCreate  # noqa: E402
from repositories.user_repository import UserRepository  # noqa: E402
from services import milestones_service, projects_service, users_service  # noqa: E402

TABLES = "audit_log, budget_history, time_entries, milestone_assignments, milestone_dependencies, milestones, projects, employees, users"


def days(n: int) -> date:
    """The date n days from today."""
    return date.today() + timedelta(days=n)


@pytest.fixture(scope="session")
def database_ready():
    """Create the test database and a fresh schema once per test run."""
    import psycopg

    try:
        admin = psycopg.connect(config.postgres_conninfo().replace(f"dbname={TEST_DB}", "dbname=postgres"),
                                autocommit=True)
    except Exception:  # noqa: BLE001
        pytest.skip("PostgreSQL is not reachable")
    cur = admin.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,))
    if cur.fetchone() is None:
        cur.execute(f'CREATE DATABASE "{TEST_DB}"')
    admin.close()

    conn = psycopg.connect(config.postgres_conninfo())
    conn.execute((SERVICE_DIR / "scripts" / "reset_db.sql").read_text())
    conn.commit()
    conn.close()
    return True


@pytest.fixture()
def clean(database_ready):
    """Empty all tables, then let init_db() create the first admin again."""
    database.reset_connection()
    database._ready = False
    with database.transaction() as db:
        db.run(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE")
    database._ready = False
    database.init_db()


def call(fn, *args):
    """Run a service function in its own transaction, like one API request."""
    with database.transaction() as db:
        return fn(db, *args)


def fails(status: int, fn, *args) -> ApiError:
    """Assert a service call fails with this HTTP status; return the error."""
    with pytest.raises(ApiError) as caught:
        call(fn, *args)
    assert caught.value.status == status, caught.value.message
    return caught.value


def who(user_id: int):
    """The user as an Admin/Manager/Employee object (re-read so it's never stale)."""
    with database.transaction() as db:
        return user_from_row(UserRepository(db).find_by_id(user_id))


def new_user(admin, role: str, name: str, **extra) -> int:
    handle = name.lower().replace(" ", ".")
    body = UserCreate(name=name, email=f"{handle}@acme.example", role=role,
                      **({"title": "Engineer", "salary": 104000} if role == "employee" else {}), **extra)
    return call(users_service.create_user, admin, body)["user"]["id"]


@pytest.fixture()
def org(clean):
    """Two managers, three employees, and a project run by manager m1.

    Employee salary 104,000 -> hourly rate exactly 50.00.
    """
    admin = who(1)
    m1 = new_user(admin, "manager", "Maria Manager")
    m2 = new_user(admin, "manager", "Omar Other")
    e1 = new_user(admin, "employee", "Eve Employee", manager_id=m1)
    e2 = new_user(admin, "employee", "Ed Second", manager_id=m1)
    e3 = new_user(admin, "employee", "Zoe Elsewhere", manager_id=m2)
    project = call(projects_service.create_project, admin, ProjectCreate(
        title="Server decommission", description="Retire 1000 servers", start_date=days(-60),
        end_date=days(300), budget=50000, estimated_hours=2000, manager_id=m1))
    milestone = call(milestones_service.create_milestone, who(m1), project["id"], MilestoneCreate(
        title="First 200 servers", description="200 servers retired", start_date=days(-30), end_date=days(30)))
    return {"admin": 1, "m1": m1, "m2": m2, "e1": e1, "e2": e2, "e3": e3,
            "project": project["id"], "milestone": milestone["id"]}
