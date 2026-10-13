"""Business rules, tested through the services against a real PostgreSQL database."""

from datetime import timedelta

import pytest

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

    def test_tokens(self, clean):
        tokens = call(auth_service.login, "admin", "Admin@123")
        assert call(auth_service.current_user, tokens["access_token"]).role == "admin"
        fails(401, auth_service.current_user, tokens["refresh_token"])   # refresh != access
        fails(401, auth_service.current_user, "garbage")
        assert call(auth_service.refresh, tokens["refresh_token"])["access_token"]

    def test_archived_user_is_locked_out(self, org):
        password = call(users_service.reset_password, who(1), org["e1"])["temporary_password"]
        token = call(auth_service.login, "eve.employee", password)["access_token"]
        call(users_service.archive_user, who(1), org["e1"])
        fails(401, auth_service.current_user, token)          # existing session ends immediately
        fails(401, auth_service.login, "eve.employee", password)

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
    def test_create_gives_six_char_password(self, clean):
        result = call(users_service.create_user, who(1), UserCreate(
            name="New Hire", username="new.hire", email="new@acme.example", role="employee", salary=52000))
        assert len(result["temporary_password"]) == 6
        assert result["user"]["display_id"].startswith("E") and float(result["user"]["hourly_rate"]) == 25.0
        assert call(auth_service.login, "new.hire", result["temporary_password"])

    def test_duplicates(self, org):
        err = fails(409, users_service.create_user, who(1), UserCreate(
            name="X", username="EVE.employee", email="Eve.Employee@acme.example", role="employee"))
        assert set(err.fields) == {"username", "email"}

    def test_only_employees_have_managers(self, org):
        fails(400, users_service.create_user, who(1), UserCreate(
            name="Bad", username="bad", email="b@x.io", role="manager", manager_id=org["m1"]))
        fails(400, users_service.create_user, who(1), UserCreate(
            name="Bad", username="bad", email="b@x.io", role="employee", manager_id=org["e1"]))

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
        assert call(auth_service.login, "eve.employee", password)


# ===========================================================================
# Projects
# ===========================================================================
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
                    MilestoneCreate(title="Too long", start_date=days(0), end_date=days(999)))
        assert "end_date" in err.fields

    def test_status_comes_from_dates_and_timestamp(self, org):
        m1 = who(org["m1"])
        future = call(milestones_service.create_milestone, m1, org["project"],
                      MilestoneCreate(title="Later", start_date=days(40), end_date=days(60)))
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
                      MilestoneCreate(title="Next 200", start_date=days(0), end_date=days(60)))
        assign(org, "e1", -10, 10)
        err = fails(409, milestones_service.create_assignment, m1, second["id"],
                    AssignmentCreate(user_id=org["e1"], start_date=days(5), end_date=days(20)))
        assert "First 200 servers" in err.message and "one milestone at a time" in err.message
        assign(org, "e1", 11, 20, milestone=second["id"])   # back to back is fine

    def test_moving_an_assignment_onto_another_is_blocked(self, org):
        m1 = who(org["m1"])
        second = call(milestones_service.create_milestone, m1, org["project"],
                      MilestoneCreate(title="Next 200", start_date=days(0), end_date=days(60)))
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
