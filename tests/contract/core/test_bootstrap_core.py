import json
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from ros_xolo.core.models import (
    Empleado,
    HabilitacionSucursal,
    Organizacion,
    PermisoPlaneacion,
    Rol,
    Sucursal,
    UsuarioOrganizacion,
)
from ros_xolo.core.services.catalog_changes import CoreValidationError, validate_manifest


def test_manifest_requires_schema_version_one():
    with pytest.raises(CoreValidationError):
        validate_manifest({"schema_version": 2})


@pytest.mark.django_db(transaction=True)
def test_bootstrap_initializes_catalog_and_access_links(tmp_path):
    user_model = get_user_model()
    operator = user_model.objects.create_superuser("operador-inicial", password="not-for-production")
    planner = user_model.objects.create_user("planeador-piloto", password="not-for-production")
    employee_login = user_model.objects.create_user("empleado-piloto", password="not-for-production")
    ids = {name: str(uuid4()) for name in (
        "organization", "branch", "employee", "membership", "role", "area", "station",
        "shift", "planner_link", "employee_link", "planner_grant",
    )}
    manifest = {
        "schema_version": 1,
        "organization_id": ids["organization"],
        "organization_name": "Organización piloto",
        "expected_core_revision": 0,
        "branches": [{"id": ids["branch"], "name": "Jaltepec", "timezone": "America/Mexico_City"}],
        "employees": [{"id": ids["employee"], "display_name": "Empleado piloto"}],
        "memberships": [{"id": ids["membership"], "employee_id": ids["employee"], "branch_id": ids["branch"]}],
        "roles": [{"id": ids["role"], "name": "Operación", "applicable_branch_ids": [ids["branch"]]}],
        "areas": [{"id": ids["area"], "branch_id": ids["branch"], "name": "Piso"}],
        "stations": [{"id": ids["station"], "branch_id": ids["branch"], "area_id": ids["area"], "name": "Estación 1"}],
        "shifts": [{"id": ids["shift"], "name": "Diurno", "start_local_time": "09:00", "end_local_time": "17:00", "applicable_branch_ids": [ids["branch"]]}],
        "user_links": [
            {"id": ids["planner_link"], "username": planner.username},
            {"id": ids["employee_link"], "username": employee_login.username, "employee_id": ids["employee"]},
        ],
        "planner_grants": [{"id": ids["planner_grant"], "username": planner.username, "branch_id": ids["branch"]}],
    }
    manifest_path = tmp_path / "pilot-core.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    call_command("bootstrap_core", "--input", str(manifest_path), "--actor", operator.username)

    organization = Organizacion.objects.get(pk=ids["organization"])
    branch = Sucursal.objects.get(pk=ids["branch"])
    assert organization.core_revision == 1
    assert Empleado.objects.filter(pk=ids["employee"], organization=organization).exists()
    assert HabilitacionSucursal.objects.filter(employee_id=ids["employee"], branch=branch).exists()
    assert Rol.objects.get(pk=ids["role"]).applicable_branches.get() == branch
    assert UsuarioOrganizacion.objects.filter(user=employee_login, employee_id=ids["employee"]).exists()
    assert PermisoPlaneacion.objects.filter(user=planner, branch=branch, enabled=True).exists()


@pytest.mark.django_db(transaction=True)
def test_bootstrap_rolls_back_the_initial_organization_for_invalid_references(tmp_path):
    operator = get_user_model().objects.create_superuser("operator", password="not-for-production")
    organization_id = str(uuid4())
    manifest_path = tmp_path / "invalid-pilot-core.json"
    manifest_path.write_text(json.dumps({
        "schema_version": 1,
        "organization_id": organization_id,
        "organization_name": "No debe persistir",
        "memberships": [{"id": str(uuid4()), "employee_id": str(uuid4()), "branch_id": str(uuid4())}],
    }), encoding="utf-8")

    with pytest.raises(CoreValidationError):
        call_command("bootstrap_core", "--input", str(manifest_path), "--actor", operator.username)

    assert not Organizacion.objects.filter(pk=organization_id).exists()
