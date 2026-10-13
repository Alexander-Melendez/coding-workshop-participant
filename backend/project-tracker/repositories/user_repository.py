"""SQL for users and employees."""

from db import Database

# A user plus their employee details (NULL for admins and managers)
USER_SELECT = """
SELECT u.id, u.email, u.username, u.name, u.password_hash, u.role, u.archived_at, u.created_at,
       e.id AS employee_id, e.title, e.salary, e.manager_id,
       boss.name AS manager_name
FROM users u
LEFT JOIN employees e ON e.user_id = u.id
LEFT JOIN users boss ON boss.id = e.manager_id
"""


class UserRepository:
    def __init__(self, db: Database):
        self.db = db

    def find_by_id(self, user_id: int) -> dict | None:
        return self.db.one(USER_SELECT + " WHERE u.id = %s", (user_id,))

    def find_by_login(self, username_or_email: str) -> dict | None:
        login = username_or_email.lower()
        return self.db.one(USER_SELECT + " WHERE lower(u.username) = %s OR lower(u.email) = %s", (login, login))

    def find_by_employee_id(self, employee_id: int) -> dict | None:
        return self.db.one(USER_SELECT + " WHERE e.id = %s", (employee_id,))

    def search(self, *, archived: bool | None, role: str | None = None, manager_id: int | None = None,
               text: str | None = None) -> list[dict]:
        """List users. archived: True = only archived, False = only active, None = both."""
        where = ["TRUE"]
        params: list = []
        if archived is True:
            where.append("u.archived_at IS NOT NULL")
        if archived is False:
            where.append("u.archived_at IS NULL")
        if role:
            where.append("u.role = %s")
            params.append(role)
        if manager_id:
            where.append("e.manager_id = %s")
            params.append(manager_id)
        if text:
            where.append("(u.name ILIKE %s OR u.username ILIKE %s OR u.email ILIKE %s OR e.title ILIKE %s)")
            params += [f"%{text}%"] * 4
        sql = USER_SELECT + " WHERE " + " AND ".join(where) + " ORDER BY u.role, u.name"
        return self.db.all(sql, params)

    def username_taken(self, username: str, except_id: int = 0) -> bool:
        return self.db.one("SELECT id FROM users WHERE lower(username) = lower(%s) AND id <> %s",
                           (username, except_id)) is not None

    def email_taken(self, email: str, except_id: int = 0) -> bool:
        return self.db.one("SELECT id FROM users WHERE lower(email) = lower(%s) AND id <> %s",
                           (email, except_id)) is not None

    def create(self, email: str, username: str, name: str, password_hash: str, role: str) -> int:
        return self.db.value(
            "INSERT INTO users (email, username, name, password_hash, role) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (email, username, name, password_hash, role),
        )

    def create_employee(self, user_id: int, title: str | None, salary, manager_id: int | None) -> int:
        return self.db.value(
            "INSERT INTO employees (user_id, title, salary, manager_id) VALUES (%s, %s, %s, %s) RETURNING id",
            (user_id, title, salary, manager_id),
        )

    def update_user(self, user_id: int, name: str, email: str, username: str, role: str) -> None:
        self.db.run("UPDATE users SET name = %s, email = %s, username = %s, role = %s WHERE id = %s",
                    (name, email, username, role, user_id))

    def update_employee(self, user_id: int, title: str | None, salary, manager_id: int | None) -> None:
        self.db.run("UPDATE employees SET title = %s, salary = %s, manager_id = %s WHERE user_id = %s",
                    (title, salary, manager_id, user_id))

    def set_password(self, user_id: int, password_hash: str) -> None:
        self.db.run("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))

    def archive(self, user_id: int) -> None:
        self.db.run("UPDATE users SET archived_at = now() WHERE id = %s", (user_id,))

    def restore(self, user_id: int) -> None:
        self.db.run("UPDATE users SET archived_at = NULL WHERE id = %s", (user_id,))

    def count_active_admins(self) -> int:
        return self.db.value("SELECT COUNT(*) FROM users WHERE role = 'admin' AND archived_at IS NULL")

    def has_active_team(self, manager_id: int) -> bool:
        return self.db.one(
            "SELECT e.id FROM employees e JOIN users u ON u.id = e.user_id "
            "WHERE e.manager_id = %s AND u.archived_at IS NULL LIMIT 1",
            (manager_id,),
        ) is not None

    def current_assignments(self, employee_ids: list[int]) -> dict[int, dict]:
        """What each employee is working on today, keyed by employees.id."""
        if not employee_ids:
            return {}
        rows = self.db.all(
            """
            SELECT a.employee_id, a.end_date, m.id AS milestone_id, m.title AS milestone_title,
                   p.id AS project_id, p.title AS project_title
            FROM milestone_assignments a
            JOIN milestones m ON m.id = a.milestone_id
            JOIN projects p ON p.id = m.project_id
            WHERE a.employee_id = ANY(%s) AND a.start_date <= CURRENT_DATE AND a.end_date >= CURRENT_DATE
            """,
            (employee_ids,),
        )
        return {row["employee_id"]: row for row in rows}

    def hours_between(self, employee_ids: list[int], start, end) -> dict[int, float]:
        """Hours logged per employee between two dates, keyed by employees.id."""
        if not employee_ids:
            return {}
        rows = self.db.all(
            "SELECT employee_id, SUM(hours) AS hours FROM time_entries "
            "WHERE employee_id = ANY(%s) AND work_date BETWEEN %s AND %s GROUP BY employee_id",
            (employee_ids, start, end),
        )
        return {row["employee_id"]: row["hours"] for row in rows}
