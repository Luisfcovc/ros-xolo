from django.db import transaction
from django.utils import timezone
from ros_xolo.core.events.registry import dispatch
from ros_xolo.core.models import Auditoria, Evento
from ros_xolo.core.services.locking import organization_lock


class CoreValidationError(ValueError): pass


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise CoreValidationError("schema_version debe ser 1.")
    if "organization_id" not in manifest:
        raise CoreValidationError("organization_id es obligatorio.")
    for name in ("branches", "employees", "memberships", "roles", "areas", "stations", "shifts", "user_links", "planner_grants"):
        if name in manifest and not isinstance(manifest[name], list):
            raise CoreValidationError(f"{name} debe ser una lista.")
    return manifest


def apply_core_changes(actor, manifest, expected_core_revision, applier=None):
    validate_manifest(manifest)
    if str(manifest["organization_id"]) != str(actor.organization_id): raise CoreValidationError("organization_id incompatible.")
    with organization_lock(actor.organization_id) as organization:
        if organization.core_revision != expected_core_revision: raise CoreValidationError("stale_core_revision")
        with transaction.atomic():
            if applier: applier(organization, manifest)
            organization.core_revision += 1
            organization.save(update_fields=["core_revision"])
            event = Evento.objects.create(organization=organization, actor_id=actor.user_id, type="core.catalog_changed", subject_id=organization.id, payload={"revision": organization.core_revision})
            Auditoria.objects.create(organization=organization, actor_id=actor.user_id, operation="core.apply", subject_id=organization.id, after={"revision": organization.core_revision})
            dispatch(event)
            return organization.core_revision
