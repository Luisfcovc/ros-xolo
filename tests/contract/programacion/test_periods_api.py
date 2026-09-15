"""T025 contract coverage for the implemented planning API."""


def test_create_period_requires_authenticated_planner(client):
    response = client.post("/api/v1/planning/periods", data={"branch_id": "00000000-0000-0000-0000-000000000000", "date_from": "2026-09-14", "date_to": "2026-09-20"}, content_type="application/json")
    assert response.status_code == 401
