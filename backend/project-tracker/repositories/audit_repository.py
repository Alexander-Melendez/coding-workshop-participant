"""SQL for the audit log. Rows are only ever added, never changed."""

import json
from datetime import date, datetime
from decimal import Decimal

from db import Database

# Never copied into the audit log
HIDDEN_FIELDS = {"password_hash"}


def _json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def changed_fields(before: dict | None, after: dict | None) -> dict | None:
    """Keep only the fields that changed, e.g. {"before": {"budget": 1}, "after": {"budget": 2}}."""
    before = {k: v for k, v in (before or {}).items() if k not in HIDDEN_FIELDS} if before is not None else None
    after = {k: v for k, v in (after or {}).items() if k not in HIDDEN_FIELDS} if after is not None else None
    if before is None or after is None:
        return {"before": before, "after": after} if (before or after) else None
    keys = [k for k in after if before.get(k) != after.get(k)]
    if not keys:
        return None
    return {"before": {k: before.get(k) for k in keys}, "after": {k: after.get(k) for k in keys}}


class AuditRepository:
    def __init__(self, db: Database):
        self.db = db

    def add(self, actor, action: str, entity_type: str, entity_id: int | None, summary: str,
            before: dict | None = None, after: dict | None = None) -> None:
        """Record one action. `actor` is the signed-in user (or None for failed logins/system)."""
        changes = changed_fields(before, after)
        self.db.run(
            "INSERT INTO audit_log (actor_id, actor_role, action, entity_type, entity_id, summary, changes) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                getattr(actor, "id", None),
                getattr(actor, "role", None),
                action,
                entity_type,
                entity_id,
                summary,
                json.dumps(changes, default=_json_value) if changes else None,
            ),
        )

    def search(self, where: list[str], params: list, limit: int, offset: int) -> tuple[list[dict], int]:
        base = " FROM audit_log a LEFT JOIN users u ON u.id = a.actor_id WHERE " + " AND ".join(where or ["TRUE"])
        total = self.db.value("SELECT COUNT(*)" + base, params)
        rows = self.db.all(
            "SELECT a.id, a.actor_id, a.actor_role, u.name AS actor_name, a.action, a.entity_type, a.entity_id,"
            " a.summary, a.changes, a.created_at" + base + " ORDER BY a.created_at DESC, a.id DESC LIMIT %s OFFSET %s",
            [*params, limit, offset],
        )
        return rows, total

    def distinct(self, column: str) -> list[str]:
        """All values used so far in a column (for the filter dropdowns)."""
        if column not in ("action", "entity_type"):
            raise ValueError(column)
        rows = self.db.all(f"SELECT DISTINCT {column} AS value FROM audit_log ORDER BY 1")  # noqa: S608 - allow-listed
        return [row["value"] for row in rows]

    def recent(self, limit: int = 8) -> list[dict]:
        return self.db.all(
            "SELECT a.id, a.action, a.entity_type, a.entity_id, a.summary, a.created_at, u.name AS actor_name "
            "FROM audit_log a LEFT JOIN users u ON u.id = a.actor_id ORDER BY a.created_at DESC, a.id DESC LIMIT %s",
            (limit,),
        )
