"""Business rules, tested through the services against a real PostgreSQL database."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

import security
from models.schemas import (
    AssignmentCreate,
    AssignmentUpdate,
    ManagerChange,
    MilestoneCreate,
    MilestoneUpdate,
    PasswordChange,
    ProfileUpdate,
    ProjectCreate,
    ProjectUpdate,
    TimeEntryCreate,
    TimeEntryUpdate,
    UserCreate,
    UserUpdate,
)
from services import (
    audit_service,
    auth_service,
    dashboard_service,
    milestones_service,
    projects_service,
    time_service,
    users_service,
)
import db as database
from repositories.user_repository import UserRepository
from tests.conftest import call, days, fails, new_user, who


def assign(org, employee, start=-20, end=20, milestone=None, by="m1"):
    return call(milestones_service.create_assignment, who(org[by]), milestone or org["milestone"],
                AssignmentCreate(user_id=org[employee], start_date=days(start), end_date=days(end)))


def log(org, employee, day, hours=8, milestone=None):
    return call(time_service.create_entry, who(org[employee]),
                TimeEntryCreate(milestone_id=milestone or org["milestone"], work_date=days(day), hours=hours))


# ===========================================================================
# Sign-in
# ===========================================================================
class TestAuth:
    def test_first_admin_is_created(self, clean):
        result = call(auth_service.login, "admin", "Admin@123")
        assert result["user"]["display_id"] == "A000001" and result["token_type"] == "bearer"

    def test_login_by_email_any_case(self, clean):
        assert call(auth_service.login, "ADMIN@acme.example", "Admin@123")["access_token"]

    def test_wrong_password_is_401_and_audited(self, clean):
        fails(401, auth_service.login, "admin", "nope")
        logs = call(audit_service.list_audit_log, "login_failed", None, None, None, None, 50, 0)
        assert logs["total"] == 1

    def test_logout_is_audited(self, org):
        call(auth_service.logout, who(org["e1"]))
        logs = call(audit_service.list_audit_log, "logout", None, None, None, None, 50, 0)
        assert logs["total"] == 1
        entry = logs["items"][0]
        assert entry["actor_id"] == org["e1"] and entry["summary"] == "Eve Employee signed out"

    def test_tokens(self, clean):
        tokens = call(auth_service.login, "admin", "Admin@123")
        assert call(auth_service.current_user, tokens["access_token"]).role == "admin"
        fails(401, auth_service.current_user, tokens["refresh_token"])   # refresh != access
        fails(401, auth_service.current_user, "garbage")
        assert call(auth_service.refresh, tokens["refresh_token"])["access_token"]

    def test_archived_user_is_locked_out(self, org):
        password = call(users_service.reset_password, who(1), org["e1"])["temporary_password"]
        token = call(auth_service.login, "eve.employee@acme.example", password)["access_token"]
        call(users_service.archive_user, who(1), org["e1"])
        fails(401, auth_service.current_user, token)          # existing session ends immediately
        fails(401, auth_service.login, "eve.employee@acme.example", password)

    def test_profile_and_password(self, org):
        eve = who(org["e1"])
        me = call(auth_service.update_profile, eve, ProfileUpdate(name="Eve A", email="EVE@acme.example"))
        assert me["name"] == "Eve A" and me["email"] == "eve@acme.example"
        fails(400, auth_service.change_password, eve,
              PasswordChange(current_password="bad", new_password="longenough1"))


# ===========================================================================
# People and permissions
# ===========================================================================
class TestUsers:
    def test_create_generates_username_and_password(self, clean):
        result = call(users_service.create_user, who(1), UserCreate(
            name="New Hire", email="new@acme.example", role="employee", salary=52000))
        username = result["user"]["username"]
        assert len(username) == 6 and set(username) <= set(security.USERNAME_CHARACTERS)
        assert len(result["temporary_password"]) == 6
        assert result["user"]["display_id"].startswith("E") and float(result["user"]["hourly_rate"]) == 25.0
        assert call(auth_service.login, username, result["temporary_password"])
        assert call(auth_service.login, "new@acme.example", result["temporary_password"])  # email works too

    def test_username_retries_on_collision(self, org, monkeypatch):
        taken = call(users_service.get_user, who(1), org["e1"])["username"]
        picks = iter([taken, taken, "fresh9"])
        monkeypatch.setattr(security, "generate_username", lambda: next(picks))
        result = call(users_service.create_user, who(1), UserCreate(name="X", email="x@acme.example", role="manager"))
        assert result["user"]["username"] == "fresh9"

    def test_username_gives_up_after_many_collisions(self, org, monkeypatch):
        taken = call(users_service.get_user, who(1), org["e1"])["username"]
        monkeypatch.setattr(security, "generate_username", lambda: taken)
        fails(409, users_service.create_user, who(1), UserCreate(name="X", email="x@acme.example", role="manager"))

    def test_usernames_cannot_be_chosen_or_changed(self, org):
        with pytest.raises(ValidationError):
            UserCreate(name="X", username="eve", email="x@acme.example", role="employee")
        with pytest.raises(ValidationError):
            UserUpdate(username="eve")

    def test_duplicate_email(self, org):
        err = fails(409, users_service.create_user, who(1), UserCreate(
            name="X", email="Eve.Employee@acme.example", role="employee"))
        assert set(err.fields) == {"email"}

    def test_only_employees_have_managers(self, org):
        fails(400, users_service.create_user, who(1), UserCreate(
            name="Bad", email="b@x.io", role="manager", manager_id=org["m1"]))
        fails(400, users_service.create_user, who(1), UserCreate(
            name="Bad", email="b@x.io", role="employee", manager_id=org["e1"]))

    def test_manager_sees_only_own_team_and_salaries(self, org):
        team = call(users_service.list_users, who(org["m1"]), None, None, "active", None)
        assert {u["name"] for u in team} == {"Eve Employee", "Ed Second"}
        assert all("salary" in u for u in team)
        fails(403, users_service.get_user, who(org["m1"]), org["e3"])

    def test_manager_edits_team_but_not_role(self, org):
        m1 = who(org["m1"])
        updated = call(users_service.update_user, m1, org["e1"], UserUpdate(salary=120000, title="Lead"))
        assert float(updated["salary"]) == 120000 and updated["title"] == "Lead"
        fails(403, users_service.update_user, m1, org["e1"], UserUpdate(role="manager"))
        fails(403, users_service.update_user, m1, org["e3"], UserUpdate(name="X"))

    def test_salary_cannot_be_cleared_to_null(self, org):
        err = fails(400, users_service.update_user, who(org["m1"]), org["e1"], UserUpdate(salary=None))
        assert "salary" in err.fields

    def test_employee_cannot_edit_others(self, org):
        fails(403, users_service.update_user, who(org["e1"]), org["e2"], UserUpdate(name="X"))

    def test_admin_moves_employee_to_another_manager(self, org):
        updated = call(users_service.update_user, who(1), org["e1"], UserUpdate(manager_id=org["m2"]))
        assert updated["manager_name"] == "Omar Other"

    def test_admin_cannot_demote_self(self, org):
        fails(403, users_service.update_user, who(1), 1, UserUpdate(role="employee"))

    def test_archive_rules(self, org):
        admin = who(1)
        fails(409, users_service.archive_user, admin, 1)                 # not yourself
        err = fails(409, users_service.archive_user, admin, org["m1"])    # has a team
        assert "employees" in err.message
        call(users_service.archive_user, admin, org["e3"])
        active = call(users_service.list_users, admin, None, None, "active", None)
        assert org["e3"] not in {u["id"] for u in active}
        archived = call(users_service.list_users, admin, None, None, "archived", None)
        assert [u["id"] for u in archived] == [org["e3"]]
        call(users_service.restore_user, admin, org["e3"])

    def test_reset_password(self, org):
        password = call(users_service.reset_password, who(1), org["e1"])["temporary_password"]
        assert call(auth_service.login, "eve.employee@acme.example", password)


# ===========================================================================
# Projects
# ===========================================================================
class TestMyTeam:
    def test_employee_sees_manager_and_teammates_only(self, org):
        team = call(users_service.my_team, who(org["e1"]))
        assert team["manager"]["name"] == "Maria Manager" and team["manager"]["display_id"].startswith("M")
        assert {(t["name"], t["is_me"]) for t in team["teammates"]} == {("Eve Employee", True), ("Ed Second", False)}
        # contact details only: no salary, username or workload
        assert set(team["teammates"][0]) == {"id", "display_id", "role", "name", "email", "title", "is_me"}

    def test_archived_teammates_are_hidden(self, org):
        call(users_service.archive_user, who(1), org["e2"])
        names = {t["name"] for t in call(users_service.my_team, who(org["e1"]))["teammates"]}
        assert names == {"Eve Employee"}

    def test_employee_without_manager(self, org):
        call(users_service.update_user, who(1), org["e1"], UserUpdate(manager_id=None))
        assert call(users_service.my_team, who(org["e1"])) == {"manager": None, "teammates": []}

    def test_can_view_user_rules(self, org):
        eve = who(org["e1"])
        with database.transaction() as db:
            users = UserRepository(db)
            assert eve.can_view_user(users.find_by_id(org["m1"]))      # her manager
            assert eve.can_view_user(users.find_by_id(org["e2"]))      # teammate
            assert not eve.can_view_user(users.find_by_id(org["e3"]))  # another manager's team
            assert not eve.can_view_user(users.find_by_id(org["m2"]))  # another manager
            assert not eve.can_view_salary(users.find_by_id(org["e2"]))


class TestProjects:
    def test_manager_must_be_a_manager(self, org):
        err = fails(400, projects_service.create_project, who(1), ProjectCreate(
            title="P", start_date=days(0), end_date=days(9), budget=1, manager_id=org["e1"]))
        assert "manager_id" in err.fields

    def test_end_before_start(self, org):
        fails(400, projects_service.create_project, who(1), ProjectCreate(
            title="P", start_date=days(9), end_date=days(0), budget=1, manager_id=org["m1"]))

    def test_visibility(self, org):
        pid = org["project"]
        assert [p["id"] for p in call(projects_service.list_projects, who(org["m1"]), None, None, None, False)] == [pid]
        assert call(projects_service.list_projects, who(org["m2"]), None, None, None, False) == []
        fails(403, projects_service.get_project, who(org["m2"]), pid)
        assert call(projects_service.list_projects, who(org["e1"]), None, None, None, False) == []
        assign(org, "e1")
        projects = call(projects_service.list_projects, who(org["e1"]), None, None, None, False)
        assert [p["id"] for p in projects] == [pid] and "budget" not in projects[0]

    def test_permissions_tell_the_ui_what_to_show(self, org):
        as_manager = call(projects_service.get_project, who(org["m1"]), org["project"])["permissions"]
        assert as_manager["can_edit"] and as_manager["can_manage_milestones"] and not as_manager["can_archive"]
        assign(org, "e1")
        as_employee = call(projects_service.get_project, who(org["e1"]), org["project"])["permissions"]
        assert not as_employee["can_edit"] and not as_employee["can_manage_milestones"]
        assert as_employee["can_log_time"]

    def test_budget_change_needs_reason_and_is_recorded(self, org):
        m1, pid = who(org["m1"]), org["project"]
        err = fails(400, projects_service.update_project, m1, pid, ProjectUpdate(budget=60000))
        assert "budget_change_reason" in err.fields
        call(projects_service.update_project, m1, pid, ProjectUpdate(budget=60000, budget_change_reason="More scope"))
        history = call(projects_service.budget_history, m1, pid)
        assert [(float(h["old_budget"]), float(h["new_budget"]), h["reason"]) for h in history] == [
            (50000, 60000, "More scope"), (0, 50000, "Starting budget")]

    def test_dates_must_contain_milestones(self, org):
        err = fails(400, projects_service.update_project, who(org["m1"]), org["project"],
                    ProjectUpdate(end_date=days(1)))
        assert "First 200 servers" in err.message

    def test_complete_and_archive_lifecycle(self, org):
        m1, admin, pid = who(org["m1"]), who(1), org["project"]
        fails(409, projects_service.complete_project, m1, pid)            # milestone still open
        fails(409, projects_service.archive_project, admin, pid)          # not completed yet
        call(milestones_service.complete_milestone, m1, org["milestone"])
        project = call(projects_service.complete_project, m1, pid)
        assert project["completed_at"] and project["health"] == "green"
        fails(409, projects_service.update_project, m1, pid, ProjectUpdate(title="x"))   # read-only now
        call(projects_service.archive_project, admin, pid)
        fails(404, projects_service.get_project, m1, pid)                 # hidden from the manager
        archived = call(projects_service.list_projects, admin, None, "archived", None, False)
        assert [p["id"] for p in archived] == [pid]

    def test_restore_needs_an_active_manager(self, org):
        m1, admin, pid = who(org["m1"]), who(1), org["project"]
        call(milestones_service.complete_milestone, m1, org["milestone"])
        call(projects_service.complete_project, m1, pid)
        call(projects_service.archive_project, admin, pid)
        for e in ("e1", "e2"):
            call(users_service.update_user, admin, org[e], UserUpdate(manager_id=org["m2"]))
        call(users_service.archive_user, admin, org["m1"])
        fails(409, projects_service.restore_project, admin, pid)
        call(projects_service.change_manager, admin, pid, ManagerChange(manager_id=org["m2"]))
        assert call(projects_service.restore_project, admin, pid)["archived_at"] is None

    def test_search_and_filters(self, org):
        admin = who(1)
        assert len(call(projects_service.list_projects, admin, "decomm", None, None, False)) == 1
        assert call(projects_service.list_projects, admin, "zzz", None, None, False) == []


# ===========================================================================
# Milestones and assignments
# ===========================================================================
class TestMilestones:
    def test_must_fit_project(self, org):
        err = fails(400, milestones_service.create_milestone, who(org["m1"]), org["project"],
                    MilestoneCreate(title="Too long", description="x", start_date=days(0), end_date=days(999)))
        assert "end_date" in err.fields

    def test_status_comes_from_dates_and_timestamp(self, org):
        m1 = who(org["m1"])
        future = call(milestones_service.create_milestone, m1, org["project"],
                      MilestoneCreate(title="Later", description="x", start_date=days(40), end_date=days(60)))
        assert future["status"] == "not_started"
        assert call(milestones_service.get_milestone, m1, org["milestone"])["status"] == "in_progress"
        done = call(milestones_service.complete_milestone, m1, org["milestone"])
        assert done["status"] == "complete" and done["locked"]

    def test_completed_milestone_is_locked(self, org):
        m1, mid = who(org["m1"]), org["milestone"]
        call(milestones_service.update_milestone, m1, mid, MilestoneUpdate(end_date=days(40)))
        call(milestones_service.complete_milestone, m1, mid)
        fails(409, milestones_service.update_milestone, m1, mid, MilestoneUpdate(end_date=days(45)))
        fails(409, milestones_service.delete_milestone, m1, mid)

    def test_employee_cannot_edit(self, org):
        fails(403, milestones_service.update_milestone, who(org["e1"]), org["milestone"], MilestoneUpdate(title="x"))

    def test_one_milestone_at_a_time(self, org):
        m1 = who(org["m1"])
        second = call(milestones_service.create_milestone, m1, org["project"],
                      MilestoneCreate(title="Next 200", description="Next 200 retired", start_date=days(0), end_date=days(60)))
        assign(org, "e1", -10, 10)
        err = fails(409, milestones_service.create_assignment, m1, second["id"],
                    AssignmentCreate(user_id=org["e1"], start_date=days(5), end_date=days(20)))
        assert "First 200 servers" in err.message and "one milestone at a time" in err.message
        assign(org, "e1", 11, 20, milestone=second["id"])   # back to back is fine

    def test_moving_an_assignment_onto_another_is_blocked(self, org):
        m1 = who(org["m1"])
        second = call(milestones_service.create_milestone, m1, org["project"],
                      MilestoneCreate(title="Next 200", description="Next 200 retired", start_date=days(0), end_date=days(60)))
        assign(org, "e1", -10, 10)
        later = assign(org, "e1", 11, 20, milestone=second["id"])
        fails(409, milestones_service.update_assignment, m1, later["id"], AssignmentUpdate(start_date=days(5)))

    def test_manager_assigns_only_own_team(self, org):
        fails(403, milestones_service.create_assignment, who(org["m1"]), org["milestone"],
              AssignmentCreate(user_id=org["e3"], start_date=days(0), end_date=days(5)))
        assign(org, "e3", 0, 5, by="admin")

    def test_assignment_must_fit_milestone(self, org):
        err = fails(400, milestones_service.create_assignment, who(org["m1"]), org["milestone"],
                    AssignmentCreate(user_id=org["e1"], start_date=days(0), end_date=days(90)))
        assert "end_date" in err.fields

    def test_completing_frees_people(self, org):
        assign(org, "e1", -5, 20)
        call(milestones_service.complete_milestone, who(org["m1"]), org["milestone"])
        milestone = call(milestones_service.get_milestone, who(org["m1"]), org["milestone"])
        assert milestone["assignments"][0]["end_date"] == days(0)

    def test_cannot_shrink_past_logged_hours(self, org):
        a = assign(org, "e1")
        log(org, "e1", -15)
        call(milestones_service.delete_assignment, who(org["m1"]), a["id"])
        err = fails(400, milestones_service.update_milestone, who(org["m1"]), org["milestone"],
                    MilestoneUpdate(start_date=days(-10)))
        assert "logged" in err.message


def milestone(org, title, start, end, depends_on=(), by="m1"):
    return call(milestones_service.create_milestone, who(org[by]), org["project"], MilestoneCreate(
        title=title, description=f"{title} done", start_date=days(start), end_date=days(end),
        depends_on=list(depends_on)))


class TestDependencies:
    """org["milestone"] ("First 200 servers") runs from day -30 to day 30."""

    def test_description_is_required(self, org):
        with pytest.raises(ValueError):
            MilestoneCreate(title="No criteria", start_date=days(0), end_date=days(5))
        with pytest.raises(ValueError):
            MilestoneUpdate(description="")
        err = fails(400, milestones_service.update_milestone, who(org["m1"]), org["milestone"],
                    MilestoneUpdate(description=None))
        assert "description" in err.fields

    def test_shows_what_it_waits_on(self, org):
        nxt = milestone(org, "Next 200", 31, 60, [org["milestone"]])
        assert nxt["depends_on"] == [{"id": org["milestone"], "title": "First 200 servers", "complete": False}]
        assert nxt["waiting_on"] == ["First 200 servers"]
        call(milestones_service.complete_milestone, who(org["m1"]), org["milestone"])
        assert call(milestones_service.get_milestone, who(org["m1"]), nxt["id"])["waiting_on"] == []

    def test_must_start_after_predecessor_ends(self, org):
        err = fails(400, milestones_service.create_milestone, who(org["m1"]), org["project"], MilestoneCreate(
            title="Too early", description="x", start_date=days(30), end_date=days(60), depends_on=[org["milestone"]]))
        assert "start_date" in err.fields

    def test_finishing_early_lets_the_next_start_early(self, org):
        call(milestones_service.complete_milestone, who(org["m1"]), org["milestone"])
        milestone(org, "Next 200", 1, 60, [org["milestone"]])   # planned end was day 30

    def test_cannot_complete_before_predecessors(self, org):
        nxt = milestone(org, "Next 200", 31, 60, [org["milestone"]])
        err = fails(409, milestones_service.complete_milestone, who(org["m1"]), nxt["id"])
        assert "First 200 servers" in err.message
        call(milestones_service.complete_milestone, who(org["m1"]), org["milestone"])
        assert call(milestones_service.complete_milestone, who(org["m1"]), nxt["id"])["status"] == "complete"

    def test_no_time_until_predecessors_complete(self, org):
        plan = milestone(org, "Plan", -60, -40)
        build = milestone(org, "Build", -39, -31, [plan["id"]])
        assign(org, "e1", -39, -31, milestone=build["id"])
        err = fails(400, time_service.create_entry, who(org["e1"]),
                    TimeEntryCreate(milestone_id=build["id"], work_date=days(-35), hours=8))
        assert "Plan" in err.message
        call(milestones_service.complete_milestone, who(org["m1"]), plan["id"])
        log(org, "e1", -35, milestone=build["id"])

    def test_waits_on_every_predecessor(self, org):
        other = milestone(org, "Permits", -30, 30)
        both = milestone(org, "Final", 31, 60, [org["milestone"], other["id"]])
        call(milestones_service.complete_milestone, who(org["m1"]), org["milestone"])
        fails(409, milestones_service.complete_milestone, who(org["m1"]), both["id"])

    def test_loops_are_rejected(self, org):
        b = milestone(org, "B", 31, 60, [org["milestone"]])
        c = milestone(org, "C", 61, 90, [b["id"]])
        err = fails(400, milestones_service.update_milestone, who(org["m1"]), org["milestone"],
                    MilestoneUpdate(depends_on=[c["id"]]))
        assert "loop" in err.message

    def test_bad_links(self, org):
        fails(400, milestones_service.update_milestone, who(org["m1"]), org["milestone"],
              MilestoneUpdate(depends_on=[org["milestone"]]))
        elsewhere = call(projects_service.create_project, who(1), ProjectCreate(
            title="Other", start_date=days(-60), end_date=days(300), budget=1000, manager_id=org["m1"]))
        foreign = call(milestones_service.create_milestone, who(org["m1"]), elsewhere["id"], MilestoneCreate(
            title="Theirs", description="x", start_date=days(-60), end_date=days(-50)))
        err = fails(400, milestones_service.create_milestone, who(org["m1"]), org["project"], MilestoneCreate(
            title="Mixed", description="x", start_date=days(40), end_date=days(50), depends_on=[foreign["id"]]))
        assert "depends_on" in err.fields

    def test_predecessor_cannot_run_into_dependent(self, org):
        milestone(org, "Next 200", 31, 60, [org["milestone"]])
        err = fails(400, milestones_service.update_milestone, who(org["m1"]), org["milestone"],
                    MilestoneUpdate(end_date=days(40)))
        assert "Next 200" in err.message and "end_date" in err.fields

    def test_removing_and_auditing_links(self, org):
        nxt = milestone(org, "Next 200", 31, 60, [org["milestone"]])
        fails(409, milestones_service.delete_milestone, who(org["m1"]), org["milestone"])
        updated = call(milestones_service.update_milestone, who(org["m1"]), nxt["id"], MilestoneUpdate(depends_on=[]))
        assert updated["depends_on"] == []
        call(milestones_service.delete_milestone, who(org["m1"]), org["milestone"])
        logs = call(audit_service.list_audit_log, "update", "milestone", None, None, None, 50, 0)
        assert logs["items"][0]["changes"]["after"]["depends_on"] == []


# ===========================================================================
# Time and money
# ===========================================================================
class TestTime:
    def test_cost_is_salary_over_2080(self, org):
        assign(org, "e1")
        entry = log(org, "e1", -1)
        assert float(entry["hourly_rate"]) == 50.0 and float(entry["cost"]) == 400.0
        project = call(projects_service.get_project, who(org["m1"]), org["project"])
        assert project["spent"] == 400.0 and project["hours_logged"] == 8.0
        assert project["team"][0]["hours"] == 8.0

    @pytest.mark.parametrize("day,field", [(1, "work_date"), (-40, "work_date")])
    def test_bad_dates(self, org, day, field):
        assign(org, "e1")
        err = fails(400, time_service.create_entry, who(org["e1"]),
                    TimeEntryCreate(milestone_id=org["milestone"], work_date=days(day), hours=8))
        assert field in err.fields

    def test_one_entry_per_day(self, org):
        assign(org, "e1")
        log(org, "e1", -1, 4)
        fails(409, time_service.create_entry, who(org["e1"]),
              TimeEntryCreate(milestone_id=org["milestone"], work_date=days(-1), hours=4))

    def test_forty_hour_week(self, org):
        assign(org, "e1")
        today = days(0)
        last_monday = -(today.weekday() + 7)
        for i in range(5):
            log(org, "e1", last_monday + i)
        err = fails(400, time_service.create_entry, who(org["e1"]),
                    TimeEntryCreate(milestone_id=org["milestone"], work_date=days(last_monday + 5), hours=1))
        assert "40" in err.message

    def test_must_be_assigned(self, org):
        fails(403, time_service.create_entry, who(org["e2"]),     # can't even see the project
              TimeEntryCreate(milestone_id=org["milestone"], work_date=days(-1), hours=8))

    def test_edit_delete_and_lock(self, org):
        assign(org, "e1")
        entry = log(org, "e1", -1, 4)
        updated = call(time_service.update_entry, who(org["e1"]), entry["id"], TimeEntryUpdate(hours=6, note="fixed"))
        assert float(updated["hours"]) == 6
        fails(403, time_service.delete_entry, who(org["e2"]), entry["id"])
        call(milestones_service.complete_milestone, who(org["m1"]), org["milestone"])
        fails(409, time_service.update_entry, who(org["e1"]), entry["id"], TimeEntryUpdate(hours=5))

    def test_over_budget_turns_red(self, org):
        assign(org, "e1")
        log(org, "e1", -1)
        m1 = who(org["m1"])
        call(projects_service.update_project, m1, org["project"], ProjectUpdate(budget=100, budget_change_reason="t"))
        project = call(projects_service.get_project, m1, org["project"])
        assert project["health"] == "red" and "Over budget" in project["risk_reasons"]
        assert [p["id"] for p in call(projects_service.list_projects, m1, None, None, "red", False)] == [org["project"]]

    def test_forecast_counts_assigned_days(self, org):
        assign(org, "e1")
        project = call(projects_service.get_project, who(org["m1"]), org["project"])
        assert project["forecast"] > 0 and project["hours_assigned"] > 0

    def test_who_sees_whose_entries_and_rates(self, org):
        assign(org, "e3", -5, 5, by="admin")          # e3 reports to m2 but works on m1's project
        log(org, "e3", -1)
        as_m1 = call(time_service.list_entries, who(org["m1"]), None, None, None, None)
        assert as_m1 and "hourly_rate" not in as_m1[0] and "cost" not in as_m1[0]
        project = call(projects_service.get_project, who(org["m1"]), org["project"])
        assert "cost" not in project["team"][0] and project["spent"] == 400.0
        assert float(call(time_service.list_entries, who(org["e3"]), None, None, None, None)[0]["cost"]) == 400
        assert float(call(time_service.list_entries, who(org["m2"]), None, None, None, None)[0]["cost"]) == 400
        assert call(time_service.list_entries, who(org["e1"]), None, None, None, None) == []


# ===========================================================================
# Dashboard and audit log
# ===========================================================================
class TestDashboardAndAudit:
    def test_dashboards(self, org):
        admin = call(dashboard_service.dashboard, who(1))
        assert admin["counts"]["managers"] == 2 and admin["recent_activity"]
        assert admin["summary"]["unassigned_employees"] == 3
        manager = call(dashboard_service.dashboard, who(org["m1"]))
        assert len(manager["team"]) == 2 and "counts" not in manager
        assign(org, "e1", -5, 5)
        employee = call(dashboard_service.dashboard, who(org["e1"]))
        assert employee["week"]["target_hours"] == 40
        assert employee["current_assignment"]["milestone_title"] == "First 200 servers"

    def test_audit_log(self, org):
        logs = call(audit_service.list_audit_log, None, "project", None, None, None, 50, 0)
        assert logs["items"][0]["action"] == "create" and logs["items"][0]["actor_display_id"] == "A000001"
        everything = call(audit_service.list_audit_log, None, None, None, None, None, 200, 0)
        assert "password_hash" not in str(everything)

    def test_every_change_is_audited(self, org):
        before = call(audit_service.list_audit_log, None, None, None, None, None, 1, 0)["total"]
        assign(org, "e1")
        log(org, "e1", -1)
        after = call(audit_service.list_audit_log, None, None, None, None, None, 1, 0)["total"]
        assert after == before + 2


def test_days_helper():
    assert days(1) - days(0) == timedelta(days=1)


def test_new_user_helper(org):
    assert new_user(who(1), "manager", "Extra Manager") > 0
