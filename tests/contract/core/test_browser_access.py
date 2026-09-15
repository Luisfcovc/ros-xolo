from django.contrib.auth import get_user_model
import pytest

from ros_xolo.core.models import Organizacion, PermisoPlaneacion, Sucursal


def test_root_redirects_anonymous_users_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"] == "/login/"


@pytest.mark.django_db
def test_login_binds_planner_to_the_organization_and_opens_planning(client):
    user = get_user_model().objects.create_user(username="planner-browser", password="test-password")
    organization = Organizacion.objects.create(name="Browser XOLO")
    branch = Sucursal.objects.create(organization=organization, name="Jaltepec", timezone="America/Mexico_City")
    PermisoPlaneacion.objects.create(organization=organization, user=user, branch=branch)

    response = client.post("/login/", {"username": user.username, "password": "test-password"})

    assert response.status_code == 302
    assert response["Location"] == "/planning/"
    assert client.session["organization_id"] == str(organization.id)
    assert client.get("/planning/").status_code == 200
