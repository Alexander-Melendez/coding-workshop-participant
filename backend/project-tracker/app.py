"""The FastAPI application.

Run locally:   uvicorn app:app --reload --port 3001
API docs:      http://localhost:3001/api/project-tracker/docs
In AWS:        function.py wraps this app with Mangum for Lambda.
"""

import logging
import time

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg import Error as DatabaseError
from psycopg import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

import config
from db import transaction
from errors import ApiError
from routers import auth_router, milestones_router, projects_router, time_router, users_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("project-tracker")

app = FastAPI(
    title="Hexpath PT API",
    description="Projects, milestones, people, time and budgets. Use **Authorize** with a token from /auth/login.",
    version="1.0.0",
    docs_url=f"{config.API_PREFIX}/docs",
    openapi_url=f"{config.API_PREFIX}/openapi.json",
)

# --- routes ------------------------------------------------------------------
health = APIRouter(tags=["Health"])


@health.get("")
@health.get("/health")
def health_check():
    """Checks the whole path: API -> Lambda -> database."""
    with transaction() as db:
        return {"status": "ok", "service": "project-tracker", "database": db.value("SELECT version()")}


for router in (health, auth_router.router, users_router.router, projects_router.router,
               milestones_router.router, time_router.router):
    app.include_router(router, prefix=config.API_PREFIX)


# --- errors: every failure leaves the API as {"error": {code, message, fields?}} ---
def error(status: int, code: str, message: str, fields: dict | None = None) -> JSONResponse:
    body = {"code": code, "message": message}
    if fields:
        body["fields"] = fields
    return JSONResponse(status_code=status, content={"error": body})


@app.exception_handler(ApiError)
def handle_api_error(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status, content=exc.to_dict())


@app.exception_handler(RequestValidationError)
def handle_validation_error(request: Request, exc: RequestValidationError):
    """Pydantic errors -> 400 with a message per field (FastAPI's default is 422)."""
    fields = {}
    for err in exc.errors():
        name = str(err["loc"][-1]) if len(err["loc"]) > 1 else "body"
        if err["type"] == "missing":
            message = "This field is required"
        elif err["type"] == "json_invalid":
            message = "The request body isn't valid JSON"
        else:
            message = err["msg"].removeprefix("Value error, ")
        fields.setdefault(name, message)
    return error(400, "validation_error", "Please correct the highlighted fields", fields)


@app.exception_handler(StarletteHTTPException)
def handle_http_error(request: Request, exc: StarletteHTTPException):
    codes = {404: "not_found", 405: "method_not_allowed"}
    return error(exc.status_code, codes.get(exc.status_code, "http_error"), str(exc.detail))


@app.exception_handler(OperationalError)
def handle_database_down(request: Request, exc: OperationalError):
    logger.error("Database unavailable: %s", exc)
    return error(503, "database_unavailable", "The database is unavailable. Please try again shortly.")


@app.exception_handler(DatabaseError)
def handle_database_error(request: Request, exc: DatabaseError):
    if getattr(exc, "sqlstate", None) == "23505":  # unique violation, e.g. two requests at once
        return error(409, "conflict", "A record with these details already exists")
    logger.exception("Database error")
    return error(500, "database_error", "A database error occurred")


@app.exception_handler(Exception)
def handle_unexpected(request: Request, exc: Exception):
    logger.exception("Unhandled error")
    return error(500, "internal_error", "Something went wrong on our side")


# --- middleware --------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """One log line per request (visible in CloudWatch). Also turns unexpected
    errors into our JSON 500 here, inside the CORS layer, so browsers can read it."""
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:  # noqa: BLE001
        logger.exception("Unhandled error")
        response = error(500, "internal_error", "Something went wrong on our side")
    logger.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code,
                (time.perf_counter() - started) * 1000)
    return response


if config.IS_LOCAL:
    # Local dev: the React app on :3000 calls the API on :3001 (a different origin).
    # In AWS, CloudFront serves both from one domain, so no CORS is needed.
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class AddPrefix:
    """The workshop's local proxy strips /api/project-tracker before forwarding;
    CloudFront keeps it. Add it back when it's missing so both work."""

    def __init__(self, asgi_app):
        self.app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Collapse "//health" (Lambda URLs end in "/") into "/health"
            path = "/" + "/".join(part for part in scope["path"].split("/") if part)
            if not path.startswith(config.API_PREFIX):
                path = config.API_PREFIX + (path if path != "/" else "")
            scope = {**scope, "path": path, "raw_path": path.encode()}
        await self.app(scope, receive, send)


app.add_middleware(AddPrefix)
