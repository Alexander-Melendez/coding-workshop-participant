"""HTTP-level tests: routes, auth dependencies, status codes and error shapes.

Business rules are covered in test_services.py; these check the FastAPI
layer on top (and the Mangum Lambda handler). Skipped if FastAPI isn't
installed.
"""

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app import app  # noqa: E402
from tests.conftest import days  # noqa: E402

API = "/api/project-tracker"


@pytest.fixture()
def client(clean):
    return TestClient(app)


def login(client, username="admin", password="Admin@123") -> dict:
    response = client.post(f"{API}/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_health_with_and_without_prefix(client):
    assert client.get(f"{API}/health").json()["status"] == "ok"
    assert client.get("/health").status_code == 200   # the local proxy strips the prefix


def test_docs_are_served(client):
    assert client.get(f"{API}/openapi.json").status_code == 200
    assert client.get(f"{API}/docs").status_code == 200


def test_login_errors_have_one_shape(client):
    response = client.post(f"{API}/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401
    assert response.json() == {"error": {"code": "unauthorized", "message": "Incorrect username or password"}}


def test_token_required(client):
    assert client.get(f"{API}/projects").status_code == 401
    assert client.get(f"{API}/projects", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_x_auth_token_fallback(client):
    token = login(client)["Authorization"].split()[1]
    assert client.get(f"{API}/auth/me", headers={"X-Auth-Token": token}).status_code == 200


def test_validation_is_400_with_fields(client):
    headers = login(client)
    response = client.post(f"{API}/projects", json={"title": "", "typo": 1}, headers=headers)
    assert response.status_code == 400
    fields = response.json()["error"]["fields"]
    assert {"title", "start_date", "end_date", "budget", "manager_id", "typo"} <= set(fields)
    assert fields["start_date"] == "This field is required"


def test_bad_query_parameter_is_400(client):
    response = client.get(f"{API}/projects", params={"health": "purple"}, headers=login(client))
    assert response.status_code == 400 and "health" in response.json()["error"]["fields"]


def test_role_checks(client):
    admin = login(client)
    created = client.post(f"{API}/users", headers=admin, json={
        "name": "Eve", "email": "eve@acme.example", "role": "employee"})
    assert created.status_code == 201
    eve = login(client, created.json()["user"]["username"], created.json()["temporary_password"])
    assert client.get(f"{API}/users", headers=eve).status_code == 403
    assert client.get(f"{API}/audit-logs", headers=eve).status_code == 403
    assert client.get(f"{API}/audit-logs", headers=admin).status_code == 200
    # employees see their own team; the route is only for employees
    team = client.get(f"{API}/users/my-team", headers=eve)
    assert team.status_code == 200 and team.json() == {"manager": None, "teammates": []}
    assert client.get(f"{API}/users/my-team", headers=admin).status_code == 403
    # signing out is recorded; without a token it's a 401
    assert client.post(f"{API}/auth/logout", headers=eve).status_code == 204
    assert client.post(f"{API}/auth/logout").status_code == 401


def test_project_crud_flow(client):
    admin = login(client)
    manager = client.post(f"{API}/users", headers=admin, json={
        "name": "Maria", "email": "maria@acme.example", "role": "manager"}).json()["user"]
    project = client.post(f"{API}/projects", headers=admin, json={
        "title": "Decommission", "start_date": str(days(-10)), "end_date": str(days(100)),
        "budget": 1000, "manager_id": manager["id"]})
    assert project.status_code == 201
    pid = project.json()["id"]
    assert client.get(f"{API}/projects/{pid}", headers=admin).json()["health"] == "white"
    assert client.get(f"{API}/projects/999999", headers=admin).status_code == 404
    response = client.delete(f"{API}/projects/{pid}", headers=admin)
    assert response.status_code == 409 and response.json()["error"]["code"] == "conflict"


def test_unknown_route_is_404_json(client):
    response = client.get(f"{API}/nope", headers=login(client))
    assert response.status_code == 404 and response.json()["error"]["code"] == "not_found"


def test_lambda_handler_with_function_url_event(clean):
    pytest.importorskip("mangum")
    from function import handler

    event = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": f"{API}/health",
        "rawQueryString": "",
        "headers": {"host": "example.lambda-url.us-east-1.on.aws", "accept": "application/json"},
        "requestContext": {
            "accountId": "anonymous", "apiId": "example", "domainName": "example.lambda-url.us-east-1.on.aws",
            "domainPrefix": "example", "requestId": "id", "routeKey": "$default", "stage": "$default",
            "time": "13/Oct/2026:00:00:00 +0000", "timeEpoch": 0,
            "http": {"method": "GET", "path": f"{API}/health", "protocol": "HTTP/1.1",
                     "sourceIp": "127.0.0.1", "userAgent": "test"},
        },
        "isBase64Encoded": False,
    }

    class Context:
        aws_request_id = "test"

    result = handler(event, Context())
    assert result["statusCode"] == 200
    assert json.loads(result["body"])["status"] == "ok"
