"""User classes: the one place that decides who may do what.

Like Account -> SavingsAccount / CheckingAccount in the banking app, the
parent class holds the shared data and the children change behaviour:

    User      every permission defaults to "no"
    ├── Employee   sees projects they're assigned to, edits own name/email, logs time
    ├── Manager    runs their projects and their own team
    └── Admin      everything, including users, archives and the audit log

Services never compare role strings; they ask the user object, for
example `user.can_manage_project(project)`.
"""

from decimal import Decimal

import config

ID_PREFIX = {"admin": "A", "manager": "M", "employee": "E"}


def display_id(role: str, user_id: int) -> str:
    """Role-prefixed ID shown in the UI, e.g. M000012."""
    return f"{ID_PREFIX.get(role, 'U')}{user_id:06d}"


def hourly_rate(salary) -> Decimal:
    """Annual salary -> hourly rate (salary / 2080), rounded to cents."""
    return (Decimal(salary or 0) / config.WORK_HOURS_PER_YEAR).quantize(Decimal("0.01"))


class User:
    """Parent class with the data every user has. Denies everything by default."""

    role = "user"
    can_manage_users = False      # create/edit/archive anyone, reset passwords
    can_create_projects = False
    can_see_archived = False
    can_read_audit_log = False
    can_log_time = False
    can_see_costs = False         # budgets and money on projects

    def __init__(self, row: dict):
        self.id = row["id"]
        self.name = row["name"]
        self.email = row["email"]
        self.username = row["username"]
        self.password_hash = row.get("password_hash")
        self.employee_id = row.get("employee_id")   # employees.id (employees only)
        self.manager_id = row.get("manager_id")     # who this employee reports to
        self.salary = row.get("salary")

    @property
    def display_id(self) -> str:
        """Role-prefixed ID, e.g. E000004."""
        return display_id(self.role, self.id)

    # projects ---------------------------------------------------------
    def project_filter(self) -> tuple[str, list]:
        """SQL condition on projects (alias p) limiting which projects this user can list."""
        return "FALSE", []

    def can_view_project(self, project: dict, assigned: bool = False) -> bool:
        """`assigned`: whether this user has any milestone assignment on the project."""
        return False

    def can_manage_project(self, project: dict) -> bool:
        """Edit the project, its budget, milestones and assignments."""
        return False

    # people -----------------------------------------------------------
    def can_view_user(self, target: dict) -> bool:
        """Everyone can see their own profile."""
        return target["id"] == self.id

    def can_view_salary(self, target: dict) -> bool:
        """Everyone can see their own salary."""
        return target["id"] == self.id

    def editable_fields(self, target: dict) -> set[str]:
        """Which fields of `target` this user may change."""
        return {"name", "email"} if target["id"] == self.id else set()

    def can_assign(self, employee: dict) -> bool:
        """May this user put `employee` on a milestone?"""
        return False


class Employee(User):
    """Sees only projects they're assigned to. Logs their own time."""

    role = "employee"
    can_log_time = True

    def project_filter(self):
        return (
            "p.id IN (SELECT m.project_id FROM milestones m "
            "JOIN milestone_assignments a ON a.milestone_id = m.id WHERE a.employee_id = %s)",
            [self.employee_id],
        )

    def can_view_project(self, project, assigned=False):
        return assigned and project["archived_at"] is None

    def can_view_user(self, target):
        """Themselves, their manager, and teammates (others with the same manager)."""
        if super().can_view_user(target):
            return True
        if target["archived_at"] or self.manager_id is None:
            return False
        return target["id"] == self.manager_id or (
            target["role"] == "employee" and target.get("manager_id") == self.manager_id)


class Manager(User):
    """Runs the projects where they are the manager; manages their own team."""

    role = "manager"
    can_see_costs = True

    def project_filter(self):
        return "p.manager_id = %s", [self.id]

    def can_view_project(self, project, assigned=False):
        return project["manager_id"] == self.id and project["archived_at"] is None

    def can_manage_project(self, project):
        return self.can_view_project(project)

    def _is_my_employee(self, target):
        return target["role"] == "employee" and target.get("manager_id") == self.id

    def can_view_user(self, target):
        return super().can_view_user(target) or (self._is_my_employee(target) and target["archived_at"] is None)

    def can_view_salary(self, target):
        return super().can_view_salary(target) or self._is_my_employee(target)

    def editable_fields(self, target):
        if self._is_my_employee(target) and target["archived_at"] is None:
            return {"name", "email", "title", "salary"}
        return super().editable_fields(target)

    def can_assign(self, employee):
        return self._is_my_employee(employee) and employee["archived_at"] is None


class Admin(User):
    """Full control."""

    role = "admin"
    can_manage_users = True
    can_create_projects = True
    can_see_archived = True
    can_read_audit_log = True
    can_see_costs = True

    def project_filter(self):
        return "TRUE", []

    def can_view_project(self, project, assigned=False):
        return True

    def can_manage_project(self, project):
        return True

    def can_view_user(self, target):
        return True

    def can_view_salary(self, target):
        return True

    def editable_fields(self, target):
        fields = {"name", "email", "role", "title", "salary", "manager_id"}  # usernames never change
        if target["id"] == self.id:
            fields.discard("role")  # can't demote yourself and lock everyone out
        return fields

    def can_assign(self, employee):
        return employee["role"] == "employee" and employee["archived_at"] is None


ROLE_CLASSES = {"admin": Admin, "manager": Manager, "employee": Employee}


def user_from_row(row: dict) -> User:
    """Build the right class (Admin, Manager or Employee) for a users row."""
    return ROLE_CLASSES[row["role"]](row)
