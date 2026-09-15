import pytest


@pytest.mark.django_db
def test_health_checks_database_connection(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
