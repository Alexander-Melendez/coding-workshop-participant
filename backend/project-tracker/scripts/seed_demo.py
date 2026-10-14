"""Fill the app with realistic demo data through the public API.

Because it goes through the API, every record obeys the same rules as the
UI (8h days, 40h weeks, one milestone at a time) and shows up in the audit
log. Works against any environment:

    python scripts/seed_demo.py                                   # local dev server / proxy
    python scripts/seed_demo.py https://dxxxx.cloudfront.net      # deployed app

Creates two managers, five employees (password Demo@1234 for all) and three
projects: one on track, one over budget, one completed.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3001").rstrip("/") + "/api/project-tracker"
ADMIN_USER = os.getenv("SEED_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "Admin@123")
DEMO_PASSWORD = "Demo@1234"
TODAY = dt.date.today()


def day(offset: int) -> str:
    """Date string `offset` days from today."""
    return str(TODAY + dt.timedelta(days=offset))


def call(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    """Call the API and return parsed JSON; exit with the API's message on failure."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)  # noqa: S310 - URL comes from the CLI
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("X-Auth-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310  # nosec B310
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{method} {path} failed ({exc.code}): {exc.read().decode()}") from exc


def login(username: str, password: str) -> str:
    """Return an access token."""
    return call("POST", "/auth/login", {"username": username, "password": password})["access_token"]


def create_person(admin: str, name: str, handle: str, role: str, job: str, salary: int,
                  manager_id: int | None = None) -> dict:
    """Create a user, set the demo password, return {'id', 'token'}.

    The server generates the username, so the demo signs in with the email.
    """
    email = f"{handle}@acme.example"
    body = {"name": name, "email": email, "role": role}
    if role == "employee":
        body.update({"title": job, "salary": salary, "manager_id": manager_id})
    created = call("POST", "/users", body, admin)
    token = login(email, created["temporary_password"])
    call("POST", "/auth/change-password",
         {"current_password": created["temporary_password"], "new_password": DEMO_PASSWORD}, token)
    print(f"  {created['user']['display_id']}  {name:<14} {role:<9} "
          f"login: {email} (or {created['user']['username']}) / {DEMO_PASSWORD}")
    return {"id": created["user"]["id"], "token": login(email, DEMO_PASSWORD)}


def log_weekdays(employee: dict, milestone_id: int, start: int, end: int, hours: float = 8) -> int:
    """Log `hours` on every weekday from day(start) to day(end) (capped at yesterday)."""
    count = 0
    for offset in range(start, min(end, -1) + 1):
        date = TODAY + dt.timedelta(days=offset)
        if date.weekday() < 5:
            call("POST", "/time-entries", {"milestone_id": milestone_id, "work_date": str(date), "hours": hours},
                 employee["token"])
            count += 1
    return count


def main() -> None:
    """Create the demo organisation."""
    print(f"Seeding {BASE}")
    admin = login(ADMIN_USER, ADMIN_PASSWORD)
    existing = call("GET", "/users", token=admin)
    if any(u["email"] == "maria@acme.example" for u in existing):
        raise SystemExit("Demo data already exists (maria@acme.example). Nothing to do.")

    print("People:")
    maria = create_person(admin, "Maria Lopez", "maria", "manager", "Infrastructure manager", 145600)
    james = create_person(admin, "James Chen", "james", "manager", "Applications manager", 139000)
    eve = create_person(admin, "Eve Adams", "eve", "employee", "Systems engineer", 98800, maria["id"])
    raj = create_person(admin, "Raj Patel", "raj", "employee", "Network engineer", 104000, maria["id"])
    lena = create_person(admin, "Lena Park", "lena", "employee", "Field technician", 72800, maria["id"])
    tom = create_person(admin, "Tom Ruiz", "tom", "employee", "Software developer", 124800, james["id"])
    ana = create_person(admin, "Ana Silva", "ana", "employee", "QA analyst", 83200, james["id"])

    def project(title: str, desc: str, start: int, end: int, budget: int, hours: int, manager_id: int) -> int:
        return call("POST", "/projects", {
            "title": title, "description": desc, "start_date": day(start), "end_date": day(end),
            "budget": budget, "estimated_hours": hours, "manager_id": manager_id,
        }, admin)["id"]

    def milestone(token: str, project_id: int, title: str, desc: str, start: int, end: int, after=()) -> int:
        return call("POST", f"/projects/{project_id}/milestones",
                    {"title": title, "description": desc, "start_date": day(start), "end_date": day(end),
                     "depends_on": list(after)}, token)["id"]

    def assign(token: str, milestone_id: int, employee: dict, start: int, end: int) -> None:
        call("POST", f"/milestones/{milestone_id}/assignments",
             {"user_id": employee["id"], "start_date": day(start), "end_date": day(end)}, token)

    print("Projects:")
    # 1. On track: the server decommission from the brief
    dc = project("Data center decommission", "Retire 1,000 legacy servers from the Dallas data center within a year.",
                 -60, 300, 450000, 6000, maria["id"])
    m_plan = milestone(maria["token"], dc, "Inventory and plan",
                       "Every server tagged with an owner and a retirement date", -60, -31)
    # Each step depends on the one before, like the Microsoft Project example in the brief
    m_first = milestone(maria["token"], dc, "First 200 servers", "200 servers wiped, unracked and recycled",
                        -30, 30, [m_plan])
    m_next = milestone(maria["token"], dc, "Next 400 servers", "Servers 201-600 retired", 31, 150, [m_first])
    milestone(maria["token"], dc, "Final 400 servers", "Data center floor empty and handed back", 151, 300, [m_next])
    assign(maria["token"], m_plan, eve, -60, -31)
    assign(maria["token"], m_first, eve, -30, 30)
    assign(maria["token"], m_first, raj, -30, 30)
    log_weekdays(eve, m_plan, -60, -31)
    call("POST", f"/milestones/{m_plan}/complete", token=maria["token"])
    log_weekdays(eve, m_first, -30, -1)
    log_weekdays(raj, m_first, -30, -1, hours=7.5)
    call("PUT", f"/projects/{dc}", {"budget": 480000,
                                    "budget_change_reason": "Added 50 servers from the Hughes acquisition"},
         maria["token"])
    print("  Data center decommission: on track")

    # 2. Over budget and behind: shows red + at risk
    pay = project("Payroll system migration", "Move payroll from the on-prem system to the new cloud provider.",
                  -45, 40, 15000, 900, james["id"])
    m_map = milestone(james["token"], pay, "Data mapping", "Every payroll field mapped and validated", -45, -10)
    # Cutover can't start until the data is mapped, so the overdue mapping blocks it
    m_cut = milestone(james["token"], pay, "Cutover", "First payroll run on the new system", -9, 40, after=[m_map])
    assign(james["token"], m_map, tom, -45, -10)
    assign(james["token"], m_map, ana, -30, -10)
    assign(james["token"], m_cut, tom, -9, 40)
    log_weekdays(tom, m_map, -45, -10)
    log_weekdays(ana, m_map, -30, -10)
    print("  Payroll system migration: over budget, overdue milestone blocking the cutover")

    # 3. Completed: shows green
    net = project("Office network refresh", "Replace switches and Wi-Fi access points in the Austin office.",
                  -120, -20, 40000, 600, maria["id"])
    m_survey = milestone(maria["token"], net, "Site survey", "Coverage map and bill of materials signed off", -120, -90)
    m_install = milestone(maria["token"], net, "Install and test", "All floors on the new network", -89, -21,
                          [m_survey])
    assign(maria["token"], m_survey, lena, -120, -90)
    assign(maria["token"], m_install, lena, -89, -21)
    log_weekdays(lena, m_survey, -120, -90)
    call("POST", f"/milestones/{m_survey}/complete", token=maria["token"])
    log_weekdays(lena, m_install, -89, -21)
    call("POST", f"/milestones/{m_install}/complete", token=maria["token"])
    call("POST", f"/projects/{net}/complete", token=maria["token"])
    print("  Office network refresh: completed")

    print("Done. Sign in as admin, maria@acme.example (manager) or eve@acme.example (employee) to see each role's view.")


if __name__ == "__main__":
    main()
