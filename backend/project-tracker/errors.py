"""Errors the services raise. app.py turns each into one JSON shape:

    {"error": {"code": "validation_error", "message": "...", "fields": {...}}}

These don't depend on FastAPI, so services can be tested without it.
"""


class ApiError(Exception):
    """Base class: an error with an HTTP status code."""

    status = 500
    code = "internal_error"

    def __init__(self, message: str, fields: dict | None = None):
        super().__init__(message)
        self.message = message
        self.fields = fields or {}

    def to_dict(self) -> dict:
        """JSON body for the response."""
        body = {"code": self.code, "message": self.message}
        if self.fields:
            body["fields"] = self.fields
        return {"error": body}


class BadRequest(ApiError):
    """400: invalid input."""

    status = 400
    code = "validation_error"


class Unauthorized(ApiError):
    """401: not signed in, or the session expired."""

    status = 401
    code = "unauthorized"


class Forbidden(ApiError):
    """403: signed in, but not allowed."""

    status = 403
    code = "forbidden"


class NotFound(ApiError):
    """404: doesn't exist (or is archived and hidden from this user)."""

    status = 404
    code = "not_found"


class Conflict(ApiError):
    """409: clashes with the current state (duplicate, overlap, locked)."""

    status = 409
    code = "conflict"
