"""Reading the audit log (admins only; the route enforces that)."""

from datetime import date

from db import Database
from errors import BadRequest
from models.entities import display_id
from repositories.audit_repository import AuditRepository


def list_audit_log(db: Database, action: str | None, entity_type: str | None, search: str | None,
                   date_from: date | None, date_to: date | None, limit: int, offset: int) -> dict:
    if not 1 <= limit <= 200 or offset < 0:
        raise BadRequest("limit must be 1-200 and offset 0 or more")
    where, params = [], []
    if action:
        where.append("a.action = %s")
        params.append(action)
    if entity_type:
        where.append("a.entity_type = %s")
        params.append(entity_type)
    if search:
        where.append("(a.summary ILIKE %s OR u.name ILIKE %s)")
        params += [f"%{search}%"] * 2
    if date_from:
        where.append("a.created_at >= %s")
        params.append(date_from)
    if date_to:
        where.append("a.created_at < %s::date + 1")
        params.append(date_to)

    repo = AuditRepository(db)
    rows, total = repo.search(where, params, limit, offset)
    for row in rows:
        row["actor_display_id"] = display_id(row["actor_role"], row["actor_id"]) if row["actor_id"] else None
    return {"items": rows, "total": total, "limit": limit, "offset": offset,
            "actions": repo.distinct("action"), "entity_types": repo.distinct("entity_type")}
