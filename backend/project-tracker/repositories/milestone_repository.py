"""SQL for milestones and milestone assignments."""

from db import Database

ASSIGNMENT_SELECT = """
SELECT a.id, a.milestone_id, a.employee_id, a.start_date, a.end_date,
       u.id AS user_id, u.name AS employee_name,
       m.title AS milestone_title, m.completed_at AS milestone_completed_at,
       p.id AS project_id, p.title AS project_title
FROM milestone_assignments a
JOIN employees e ON e.id = a.employee_id
JOIN users u ON u.id = e.user_id
JOIN milestones m ON m.id = a.milestone_id
JOIN projects p ON p.id = m.project_id
"""


class MilestoneRepository:
    def __init__(self, db: Database):
        self.db = db

    # --- milestones ---------------------------------------------------------
    def find_by_id(self, milestone_id: int) -> dict | None:
        return self.db.one("SELECT * FROM milestones WHERE id = %s", (milestone_id,))

    def for_project(self, project_id: int) -> list[dict]:
        return self.db.all("SELECT * FROM milestones WHERE project_id = %s ORDER BY start_date, id", (project_id,))

    def hours_and_cost(self, milestone_id: int) -> dict:
        return self.db.one(
            "SELECT SUM(hours) AS hours, SUM(hours * hourly_rate) AS cost FROM time_entries WHERE milestone_id = %s",
            (milestone_id,),
        )

    def create(self, project_id: int, title: str, description, start_date, end_date) -> int:
        return self.db.value(
            "INSERT INTO milestones (project_id, title, description, start_date, end_date) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (project_id, title, description, start_date, end_date),
        )

    def update(self, milestone_id: int, title: str, description, start_date, end_date) -> None:
        self.db.run(
            "UPDATE milestones SET title = %s, description = %s, start_date = %s, end_date = %s WHERE id = %s",
            (title, description, start_date, end_date, milestone_id),
        )

    def mark_completed(self, milestone_id: int) -> None:
        self.db.run("UPDATE milestones SET completed_at = now() WHERE id = %s", (milestone_id,))

    def delete(self, milestone_id: int) -> None:
        self.db.run("DELETE FROM milestone_dependencies WHERE milestone_id = %s", (milestone_id,))
        self.db.run("DELETE FROM milestone_assignments WHERE milestone_id = %s", (milestone_id,))
        self.db.run("DELETE FROM milestones WHERE id = %s", (milestone_id,))

    def has_time(self, milestone_id: int) -> bool:
        return self.db.one("SELECT id FROM time_entries WHERE milestone_id = %s LIMIT 1", (milestone_id,)) is not None

    def time_outside(self, milestone_id: int, start, end) -> bool:
        """Is any logged time on this milestone outside the given dates?"""
        return self.db.one(
            "SELECT id FROM time_entries WHERE milestone_id = %s AND (work_date < %s OR work_date > %s) LIMIT 1",
            (milestone_id, start, end),
        ) is not None

    # --- dependencies -------------------------------------------------------
    def predecessors(self, milestone_id: int) -> list[dict]:
        """Milestones that must be complete before this one can start."""
        return self.db.all(
            "SELECT m.* FROM milestone_dependencies d JOIN milestones m ON m.id = d.depends_on_id "
            "WHERE d.milestone_id = %s ORDER BY m.start_date, m.id",
            (milestone_id,),
        )

    def dependents(self, milestone_id: int) -> list[dict]:
        """Milestones that are waiting on this one."""
        return self.db.all(
            "SELECT m.* FROM milestone_dependencies d JOIN milestones m ON m.id = d.milestone_id "
            "WHERE d.depends_on_id = %s ORDER BY m.start_date, m.id",
            (milestone_id,),
        )

    def project_dependencies(self, project_id: int) -> list[dict]:
        """Every (milestone_id, depends_on_id) link in a project."""
        return self.db.all(
            "SELECT d.milestone_id, d.depends_on_id FROM milestone_dependencies d "
            "JOIN milestones m ON m.id = d.milestone_id WHERE m.project_id = %s",
            (project_id,),
        )

    def set_dependencies(self, milestone_id: int, depends_on_ids: list[int]) -> None:
        self.db.run("DELETE FROM milestone_dependencies WHERE milestone_id = %s", (milestone_id,))
        for depends_on_id in depends_on_ids:
            self.db.run("INSERT INTO milestone_dependencies (milestone_id, depends_on_id) VALUES (%s, %s)",
                        (milestone_id, depends_on_id))

    # --- assignments --------------------------------------------------------
    def assignment(self, assignment_id: int) -> dict | None:
        return self.db.one(ASSIGNMENT_SELECT + " WHERE a.id = %s", (assignment_id,))

    def assignments_for(self, milestone_id: int) -> list[dict]:
        return self.db.all(ASSIGNMENT_SELECT + " WHERE a.milestone_id = %s ORDER BY a.start_date, u.name",
                           (milestone_id,))

    def search_assignments(self, where: list[str], params: list) -> list[dict]:
        return self.db.all(ASSIGNMENT_SELECT + " WHERE " + " AND ".join(where) + " ORDER BY a.start_date, u.name",
                           params)

    def overlapping_assignment(self, employee_id: int, start, end, except_id: int = 0) -> dict | None:
        """Another assignment for this employee whose dates overlap start..end."""
        return self.db.one(
            ASSIGNMENT_SELECT + " WHERE a.employee_id = %s AND a.id <> %s AND a.start_date <= %s AND a.end_date >= %s",
            (employee_id, except_id, end, start),
        )

    def assignment_outside(self, milestone_id: int, start, end) -> dict | None:
        """An assignment on this milestone that doesn't fit inside start..end."""
        return self.db.one(
            ASSIGNMENT_SELECT + " WHERE a.milestone_id = %s AND (a.start_date < %s OR a.end_date > %s) LIMIT 1",
            (milestone_id, start, end),
        )

    def is_assigned_on(self, employee_id: int, milestone_id: int, day) -> bool:
        return self.db.one(
            "SELECT id FROM milestone_assignments WHERE employee_id = %s AND milestone_id = %s "
            "AND start_date <= %s AND end_date >= %s",
            (employee_id, milestone_id, day, day),
        ) is not None

    def create_assignment(self, milestone_id: int, employee_id: int, start, end) -> int:
        return self.db.value(
            "INSERT INTO milestone_assignments (milestone_id, employee_id, start_date, end_date) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (milestone_id, employee_id, start, end),
        )

    def update_assignment(self, assignment_id: int, start, end) -> None:
        self.db.run("UPDATE milestone_assignments SET start_date = %s, end_date = %s WHERE id = %s",
                    (start, end, assignment_id))

    def delete_assignment(self, assignment_id: int) -> None:
        self.db.run("DELETE FROM milestone_assignments WHERE id = %s", (assignment_id,))

    def end_assignments_today(self, *, milestone_id: int | None = None, employee_id: int | None = None) -> None:
        """Free people up: drop assignments that haven't started, end current ones today."""
        column, value = ("milestone_id", milestone_id) if milestone_id else ("employee_id", employee_id)
        self.db.run(f"DELETE FROM milestone_assignments WHERE {column} = %s AND start_date > CURRENT_DATE",  # noqa: S608 - fixed column name
                    (value,))
        self.db.run(f"UPDATE milestone_assignments SET end_date = CURRENT_DATE "  # noqa: S608 - fixed column name
                    f"WHERE {column} = %s AND end_date > CURRENT_DATE", (value,))
