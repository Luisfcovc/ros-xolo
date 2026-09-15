import pytest

from ros_xolo.core.models import Organizacion, Sucursal


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="planner", password="not-used-in-test")


@pytest.fixture
def organization():
    return Organizacion.objects.create(name="Organización de prueba")


@pytest.fixture
def branch(organization):
    return Sucursal.objects.create(
        organization=organization,
        name="Sucursal de prueba",
        timezone="America/Mexico_City",
    )
