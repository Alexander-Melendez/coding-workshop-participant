"""Settings read from environment variables.

Terraform injects the POSTGRES_* and IS_LOCAL variables into the Lambda
(infra/locals.tf). The defaults match the local PostgreSQL that
bin/start-dev.sh sets up.
"""

import os

IS_LOCAL = os.getenv("IS_LOCAL", "true").lower() == "true"

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_NAME = os.getenv("POSTGRES_NAME") or "postgres"
POSTGRES_USER = os.getenv("POSTGRES_USER") or "postgres"
POSTGRES_PASS = os.getenv("POSTGRES_PASS") or "postgres123"

# Every route lives under this prefix (CloudFront sends /api/project-tracker/*)
API_PREFIX = "/api/project-tracker"

# Business rules from the requirements
HOURS_PER_DAY = 8
HOURS_PER_WEEK = 40
WORK_HOURS_PER_YEAR = 2080  # 40 hours x 52 weeks: salary / 2080 = hourly rate

# Login tokens
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
REFRESH_TOKEN_HOURS = int(os.getenv("REFRESH_TOKEN_HOURS", "12"))
PASSWORD_HASH_ITERATIONS = int(os.getenv("PASSWORD_HASH_ITERATIONS", "100000"))

# First admin, created when the database has no admin yet
SEED_ADMIN_USERNAME = os.getenv("SEED_ADMIN_USERNAME", "admin")
SEED_ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "Admin@123")
SEED_ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@acme.example")


def postgres_conninfo() -> str:
    """Connection string for psycopg. Aurora in AWS requires SSL."""
    info = (
        f"host={POSTGRES_HOST} port={POSTGRES_PORT} dbname={POSTGRES_NAME} "
        f"user={POSTGRES_USER} password={POSTGRES_PASS} connect_timeout=15"
    )
    if not IS_LOCAL:
        info += " sslmode=require"
    return info
