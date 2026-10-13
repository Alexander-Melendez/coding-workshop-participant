"""SQL for projects and their budget history."""

from db import Database

PROJECT_SELECT = """
SELECT p.*, u.name AS manager_name
FROM projects p
JOIN users u ON u.id = p.manager_id
"""


class ProjectRepository:
    def __init__(self, db: Database):
        self.db = db

    def find_by_id(self, project_id: int) -> dict | None:
        return self.db.one(PROJECT_SELECT + " WHERE p.id = %s", (project_id,))

    def search(self, visibility: str, visibility_params: list, *, state: str | None = None,
               text: str | None = None) -> list[dict]:
        """List projects. `visibility` is the role's SQL filter (see entities.project_filter).

        state: active | completed | archived | all | None (= not archived)
        """
        where = [visibility]
        params = list(visibility_params)
        if state == "archived":
            where.append("p.archived_at IS NOT NULL")
        elif state != "all":
            where.append("p.archived_at IS NULL")
        if state == "active":
            where.append("p.completed_at IS NULL")
        if state == "completed":
            where.append("p.completed_at IS NOT NULL")
        if text:
            where.append("(p.title ILIKE %s OR p.description ILIKE %s)")
            params += [f"%{text}%"] * 2
        return self.db.all(PROJECT_SELECT + " WHERE " + " AND ".join(where) + " ORDER BY p.end_date, p.title", params)

    def is_assigned(self, project_id: int, employee_id: int | None) -> bool:
        """Does this employee have any milestone assignment on the project?"""
        if employee_id is None:
            return False
        return self.db.one(
            "SELECT a.id FROM milestone_assignments a JOIN milestones m ON m.id = a.milestone_id "
            "WHERE m.project_id = %s AND a.employee_id = %s LIMIT 1",
            (project_id, employee_id),
        ) is not None

    def create(self, data: dict) -> int:
        return self.db.value(
            """
            INSERT INTO projects (title, description, start_date, end_date, budget, estimated_hours, manager_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (data["title"], data["description"], data["start_date"], data["end_date"],
             data["budget"], data["estimated_hours"], data["manager_id"]),
        )

    def update(self, project_id: int, data: dict) -> None:
        self.db.run(
            """
            UPDATE projects SET title = %s, description = %s, start_date = %s, end_date = %s,
                                budget = %s, estimated_hours = %s
            WHERE id = %s
            """,
            (data["title"], data["description"], data["start_date"], data["end_date"],
             data["budget"], data["estimated_hours"], project_id),
        )

    def set_manager(self, project_id: int, manager_id: int) -> None:
        self.db.run("UPDATE projects SET manager_id = %s WHERE id = %s", (manager_id, project_id))

    def mark_completed(self, project_id: int) -> None:
        self.db.run("UPDATE projects SET completed_at = now() WHERE id = %s", (project_id,))

    def archive(self, project_id: int) -> None:
        self.db.run("UPDATE projects SET archived_at = now() WHERE id = %s", (project_id,))

    def restore(self, project_id: int) -> None:
        self.db.run("UPDATE projects SET archived_at = NULL WHERE id = %s", (project_id,))

    def active_project_titles_for_manager(self, manager_id: int) -> list[str]:
        rows = self.db.all("SELECT title FROM projects WHERE manager_id = %s AND archived_at IS NULL", (manager_id,))
        return [row["title"] for row in rows]

    # --- numbers for the project summary ----------------------------------
    def hours_and_spent(self, project_id: int) -> dict:
        """Total hours logged and money spent (hours x the rate when logged)."""
        return self.db.one(
            """
            SELECT SUM(t.hours) AS hours, SUM(t.hours * t.hourly_rate) AS spent
            FROM time_entries t
            JOIN milestones m ON m.id = t.milestone_id
            WHERE m.project_id = %s
            """,
            (project_id,),
        )

    def open_assignments(self, project_id: int) -> list[dict]:
        """Assignments on milestones that aren't complete, with each person's salary (for the forecast)."""
        return self.db.all(
            """
            SELECT a.start_date, a.end_date, e.salary
            FROM milestone_assignments a
            JOIN milestones m ON m.id = a.milestone_id
            JOIN employees e ON e.id = a.employee_id
            WHERE m.project_id = %s AND m.completed_at IS NULL
            """,
            (project_id,),
        )

    def milestone_dates(self, project_id: int) -> list[dict]:
        return self.db.all("SELECT title, start_date, end_date, completed_at FROM milestones WHERE project_id = %s",
                           (project_id,))

    def team(self, project_id: int) -> list[dict]:
        """Everyone assigned to or logging time on the project, with their hours and cost."""
        return self.db.all(
            """
            SELECT u.id, u.name, u.archived_at, e.manager_id, u.role,
                   SUM(t.hours) AS hours, SUM(t.hours * t.hourly_rate) AS cost
            FROM employees e
            JOIN users u ON u.id = e.user_id
            LEFT JOIN time_entries t
                   ON t.employee_id = e.id
                  AND t.milestone_id IN (SELECT id FROM milestones WHERE project_id = %(pid)s)
            WHERE e.id IN (SELECT a.employee_id FROM milestone_assignments a
                           JOIN milestones m ON m.id = a.milestone_id WHERE m.project_id = %(pid)s)
               OR e.id IN (SELECT t2.employee_id FROM time_entries t2
                           JOIN milestones m2 ON m2.id = t2.milestone_id WHERE m2.project_id = %(pid)s)
            GROUP BY u.id, e.manager_id
            ORDER BY u.name
            """,
            {"pid": project_id},
        )

    # --- budget history ---------------------------------------------------
    def add_budget_change(self, project_id: int, old_budget, new_budget, reason: str, changed_by: int) -> None:
        self.db.run(
            "INSERT INTO budget_history (project_id, old_budget, new_budget, reason, changed_by) "
            "VALUES (%s, %s, %s, %s, %s)",
            (project_id, old_budget, new_budget, reason, changed_by),
        )

    def budget_history(self, project_id: int) -> list[dict]:
        return self.db.all(
            """
            SELECT b.id, b.old_budget, b.new_budget, b.reason, b.changed_at, u.name AS changed_by_name
            FROM budget_history b JOIN users u ON u.id = b.changed_by
            WHERE b.project_id = %s
            ORDER BY b.changed_at DESC, b.id DESC
            """,
            (project_id,),
        )
