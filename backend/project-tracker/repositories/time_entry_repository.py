"""SQL for time entries."""

from db import Database

ENTRY_SELECT = """
SELECT t.id, t.employee_id, t.milestone_id, t.work_date, t.hours, t.hourly_rate,
       t.hours * t.hourly_rate AS cost, t.note, t.created_at,
       u.id AS user_id, u.name AS employee_name, e.manager_id AS employee_manager_id,
       m.title AS milestone_title, m.completed_at AS milestone_completed_at,
       p.id AS project_id, p.title AS project_title, p.manager_id AS project_manager_id
FROM time_entries t
JOIN employees e ON e.id = t.employee_id
JOIN users u ON u.id = e.user_id
JOIN milestones m ON m.id = t.milestone_id
JOIN projects p ON p.id = m.project_id
"""


class TimeEntryRepository:
    def __init__(self, db: Database):
        self.db = db

    def find_by_id(self, entry_id: int) -> dict | None:
        return self.db.one(ENTRY_SELECT + " WHERE t.id = %s", (entry_id,))

    def search(self, where: list[str], params: list, limit: int = 1000) -> list[dict]:
        sql = ENTRY_SELECT + " WHERE " + " AND ".join(where or ["TRUE"])
        return self.db.all(sql + " ORDER BY t.work_date DESC, t.id DESC LIMIT %s", [*params, limit])

    def logged_on(self, employee_id: int, day, except_id: int = 0) -> bool:
        return self.db.one("SELECT id FROM time_entries WHERE employee_id = %s AND work_date = %s AND id <> %s",
                           (employee_id, day, except_id)) is not None

    def hours_between(self, employee_id: int, start, end, except_id: int = 0):
        hours = self.db.value(
            "SELECT SUM(hours) FROM time_entries WHERE employee_id = %s AND work_date BETWEEN %s AND %s AND id <> %s",
            (employee_id, start, end, except_id),
        )
        return hours or 0

    def create(self, employee_id: int, milestone_id: int, work_date, hours, hourly_rate, note) -> int:
        return self.db.value(
            "INSERT INTO time_entries (employee_id, milestone_id, work_date, hours, hourly_rate, note) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (employee_id, milestone_id, work_date, hours, hourly_rate, note),
        )

    def update(self, entry_id: int, work_date, hours, note) -> None:
        self.db.run("UPDATE time_entries SET work_date = %s, hours = %s, note = %s WHERE id = %s",
                    (work_date, hours, note, entry_id))

    def delete(self, entry_id: int) -> None:
        self.db.run("DELETE FROM time_entries WHERE id = %s", (entry_id,))
