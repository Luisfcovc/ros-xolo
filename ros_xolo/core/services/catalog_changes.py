"""Atomic, manifest-driven changes to the shared Core catalogue."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from ros_xolo.core.events.registry import dispatch
from ros_xolo.core.models import (
    Area, Auditoria, Empleado, Estacion, Evento, HabilitacionSucursal,
    Organizacion, PermisoPlaneacion, Rol, Sucursal, Turno, UsuarioOrganizacion,
)
from ros_xolo.core.services.locking import organization_lock


class CoreValidationError(ValueError):
    pass


LISTS = (
    "branches",
    "employees",
    "memberships",
    "roles",
    "areas",
    "stations",
    "shifts",
    "user_links", "planner_grants",
)


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise CoreValidationError("schema_version debe ser 1.")
    if not manifest.get("organization_id"):
        raise CoreValidationError("organization_id es obligatorio.")
    for name in LISTS:
        if name in manifest and not isinstance(manifest[name], list):
            raise CoreValidationError(f"{name} debe ser una lista.")
        item_ids = []
        for item in manifest.get(name, []):
            if not isinstance(item, dict):
                raise CoreValidationError(f"{name} debe contener objetos.")
            item_ids.append(_required(item, "id", name))
        if len(item_ids) != len(set(map(str, item_ids))):
            raise CoreValidationError(f"{name} contiene IDs duplicados.")
    return manifest


def _required(item, name, list_name):
    value = item.get(name)
    if value in (None, ""):
        raise CoreValidationError(f"{list_name}.{name} es obligatorio.")
    return value


def _scoped(model, item_id, organization, list_name):
    row = model.objects.filter(pk=item_id).first()
    if row is not None and row.organization_id != organization.id:
        raise CoreValidationError(f"{list_name}.{item_id} pertenece a otra organización.")
    return row


def _upsert(model, item, organization, list_name, **defaults):
    item_id = _required(item, "id", list_name)
    row = _scoped(model, item_id, organization, list_name)
    defaults["organization"] = organization
    if row is None:
        row = model(id=item_id, **defaults)
    else:
        for key, value in defaults.items():
            setattr(row, key, value)
    try:
        row.full_clean()
        row.save()
    except (IntegrityError, ValidationError) as exc:
        raise CoreValidationError(f"{list_name}.{item_id} es inválido: {exc}") from exc
    return row


def _branch(organization, branch_id, list_name):
    try:
        return Sucursal.objects.get(pk=branch_id, organization=organization)
    except Sucursal.DoesNotExist as exc:
        raise CoreValidationError(f"{list_name}.branch_id no pertenece a la organización.") from exc


def _employee(organization, employee_id, list_name):
    try:
        return Empleado.objects.get(pk=employee_id, organization=organization)
    except Empleado.DoesNotExist as exc:
        raise CoreValidationError(
            f"{list_name}.employee_id no pertenece a la organización."
        ) from exc


def _user(username, list_name):
    user = get_user_model().objects.filter(username=username, is_active=True).first()
    if user is None:
        raise CoreValidationError(f"{list_name}.username no identifica una cuenta activa.")
    return user


def _apply_manifest(organization, manifest, actor):
    for item in manifest.get("branches", []):
        _upsert(
            Sucursal,
            item,
            organization,
            "branches",
            name=_required(item, "name", "branches"),
            timezone=_required(item, "timezone", "branches"),
            active=item.get("active", True),
        )

    for item in manifest.get("employees", []):
        _upsert(
            Empleado,
            item,
            organization,
            "employees",
            display_name=_required(item, "display_name", "employees"),
            active=item.get("active", True),
        )

    for item in manifest.get("memberships", []):
        employee = _employee(
            organization, _required(item, "employee_id", "memberships"), "memberships"
        )
        branch = _branch(organization, _required(item, "branch_id", "memberships"), "memberships")
        _upsert(
            HabilitacionSucursal,
            item,
            organization,
            "memberships",
            employee=employee,
            branch=branch,
            enabled=item.get("enabled", True),
            changed_by_id=actor.user_id,
        )

    roles = []
    for item in manifest.get("roles", []):
        row = _upsert(
            Rol,
            item,
            organization,
            "roles",
            name=_required(item, "name", "roles"),
            active=item.get("active", True),
        )
        roles.append((row, item.get("applicable_branch_ids", [])))
    for row, branch_ids in roles:
        row.applicable_branches.set([_branch(organization, value, "roles") for value in branch_ids])

    for item in manifest.get("areas", []):
        branch = _branch(organization, _required(item, "branch_id", "areas"), "areas")
        _upsert(
            Area,
            item,
            organization,
            "areas",
            branch=branch,
            name=_required(item, "name", "areas"),
            active=item.get("active", True),
        )

    for item in manifest.get("stations", []):
        branch = _branch(organization, _required(item, "branch_id", "stations"), "stations")
        try:
            area = Area.objects.get(
                pk=_required(item, "area_id", "stations"),
                organization=organization,
                branch=branch,
            )
        except Area.DoesNotExist as exc:
            raise CoreValidationError("stations.area_id no pertenece a la sucursal.") from exc
        _upsert(
            Estacion,
            item,
            organization,
            "stations",
            branch=branch,
            area=area,
            name=_required(item, "name", "stations"),
            active=item.get("active", True),
        )

    shifts = []
    for item in manifest.get("shifts", []):
        row = _upsert(
            Turno,
            item,
            organization,
            "shifts",
            name=_required(item, "name", "shifts"),
            start_local_time=_required(item, "start_local_time", "shifts"),
            end_local_time=_required(item, "end_local_time", "shifts"),
            end_day_offset=item.get("end_day_offset", 0),
            active=item.get("active", True),
        )
        shifts.append((row, item.get("applicable_branch_ids", [])))
    for row, branch_ids in shifts:
        row.applicable_branches.set(
            [_branch(organization, value, "shifts") for value in branch_ids]
        )

    for item in manifest.get("user_links", []):
        user = _user(_required(item, "username", "user_links"), "user_links")
        employee_id = item.get("employee_id")
        employee = _employee(organization, employee_id, "user_links") if employee_id else None
        _upsert(
            UsuarioOrganizacion,
            item,
            organization,
            "user_links",
            user=user,
            employee=employee,
            active=item.get("active", True),
        )

    for item in manifest.get("planner_grants", []):
        user = _user(_required(item, "username", "planner_grants"), "planner_grants")
        branch = _branch(
            organization, _required(item, "branch_id", "planner_grants"), "planner_grants"
        )
        _upsert(
            PermisoPlaneacion,
            item,
            organization,
            "planner_grants",
            user=user,
            branch=branch,
            enabled=item.get("enabled", True),
        )


def _organization(manifest):
    organization_id = manifest["organization_id"]
    row = Organizacion.objects.filter(pk=organization_id).first()
    if row is not None:
        return row
    name = manifest.get("organization_name")
    if not isinstance(name, str) or not name.strip():
        raise CoreValidationError("organization_name es obligatorio para la inicialización.")
    try:
        return Organizacion.objects.create(id=organization_id, name=name.strip())
    except IntegrityError as exc:
        raise CoreValidationError("No se pudo crear la organización inicial.") from exc


def apply_core_changes(actor, manifest, expected_core_revision, applier=None):
    validate_manifest(manifest)
    with transaction.atomic():
        organization = _organization(manifest)
        if str(manifest["organization_id"]) != str(actor.organization_id):
            raise CoreValidationError("organization_id incompatible.")
        with organization_lock(organization.id) as locked:
            if locked.core_revision != expected_core_revision:
                raise CoreValidationError("stale_core_revision")
            _apply_manifest(locked, manifest, actor)
            if applier:
                applier(locked, manifest)
            locked.core_revision += 1
            locked.save(update_fields=["core_revision"])
            event = Evento.objects.create(
                organization=locked,
                actor_id=actor.user_id,
                type="core.catalog_changed",
                subject_id=locked.id,
                payload={"revision": locked.core_revision},
            )
            Auditoria.objects.create(
                organization=locked,
                actor_id=actor.user_id,
                operation="core.apply",
                subject_id=locked.id,
                after={"revision": locked.core_revision},
            )
            dispatch(event)
            return locked.core_revision
