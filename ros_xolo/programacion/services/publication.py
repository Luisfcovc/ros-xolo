"""Atomic immutable publication and revision service."""

import hashlib
import json
import uuid
from datetime import timedelta, timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from ros_xolo.core.models import Auditoria, Evento, HabilitacionSucursal
from ros_xolo.core.services.authorization import authorize_planner
from ros_xolo.core.services.locking import organization_lock
from ros_xolo.programacion.events.core_changes import resolve_incidents_after_publication
from ros_xolo.programacion.models import (
    CambioPublicacion,
    DescansoPublicado,
    FilaEmpleadoPublicada,
    JornadaPublicada,
    PeriodoProgramacion,
    PublicacionProgramacion,
)
from ros_xolo.programacion.services.conflicts import validate_candidate_conflicts
from ros_xolo.programacion.services.drafts import make_period_etag, require_matching_etag
from ros_xolo.programacion.services.revisions import (
    build_publication_changes,
    canonical_publication,
    canonical_publication_roster,
)
from ros_xolo.programacion.services.validation import canonical_candidate, validate_draft_payload


class EmployeeIneligibleFuture(ValueError):
    code = "employee_ineligible_future"
    action = "Retira o reasigna las jornadas futuras antes de republicar."

    def __init__(self, fields):
        super().__init__("Hay jornadas futuras de personal no elegible.")
        self.fields = fields


def _local_rfc3339(value, offset_seconds):
    zone = datetime_timezone(timedelta(seconds=offset_seconds))
    return value.replace(tzinfo=zone).isoformat()


def _stored_local(instant, offset_seconds):
    return (instant.astimezone(datetime_timezone.utc) + timedelta(seconds=offset_seconds)).replace(
        tzinfo=None
    )


def _draft_payload(draft):
    breaks_by_assignment = {}
    for row in draft.breaks.all():
        breaks_by_assignment.setdefault(row.assignment_id, []).append(
            {
                "break_id": str(row.id),
                "starts_at": _local_rfc3339(
                    _stored_local(row.starts_at, row.start_offset), row.start_offset
                ),
                "ends_at": _local_rfc3339(
                    _stored_local(row.ends_at, row.end_offset), row.end_offset
                ),
            }
        )
    return [
        {
            "assignment_id": str(row.assignment_id),
            "employee_id": str(row.employee_id),
            "starts_at": _local_rfc3339(
                _stored_local(row.starts_at, row.start_offset), row.start_offset
            ),
            "ends_at": _local_rfc3339(
                _stored_local(row.ends_at, row.end_offset), row.end_offset
            ),
            "role_id": str(row.role_id) if row.role_id else None,
            "station_id": str(row.station_id) if row.station_id else None,
            "shift_id": str(row.shift_id) if row.shift_id else None,
            "breaks": breaks_by_assignment.get(row.assignment_id, []),
        }
        for row in draft.assignments.all()
    ]


def _load_period_for_actor(actor, period_id):
    period = PeriodoProgramacion.objects.select_related("organization", "branch", "draft").get(
        pk=period_id, organization_id=actor.organization_id
    )
    authorize_planner(actor, period.branch_id)
    return period


def _publisher_label(user):
    return user.get_full_name().strip() or user.get_username()


def _roster(period, candidate):
    employee_by_id = {
        membership.employee_id: membership.employee
        for membership in HabilitacionSucursal.objects.filter(
            organization_id=period.organization_id,
            branch_id=period.branch_id,
            enabled=True,
            employee__active=True,
        ).select_related("employee")
    }
    for item in candidate:
        employee_by_id[item["employee"].id] = item["employee"]
    return sorted(
        employee_by_id.values(),
        key=lambda employee: (employee.display_name.casefold(), str(employee.id)),
    )


def _content_hash(assignments, roster):
    return hashlib.sha256(
        json.dumps(
            {"roster": roster, "assignments": assignments},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _before_publication_pointer(period, publication):
    """Fault-injection seam used by the atomic rollback test."""


def _create_snapshot(period, publication, candidate, roster):
    FilaEmpleadoPublicada.objects.bulk_create(
        [
            FilaEmpleadoPublicada(
                organization_id=period.organization_id,
                publication=publication,
                employee=employee,
                employee_label=employee.display_name,
                display_order=index,
            )
            for index, employee in enumerate(roster)
        ]
    )
    for item in candidate:
        JornadaPublicada.objects.create(
            organization_id=period.organization_id,
            publication=publication,
            assignment_id=item["assignment_id"],
            employee=item["employee"],
            branch_id=period.branch_id,
            starts_at=item["starts_at"],
            ends_at=item["ends_at"],
            start_local=item["start_local"],
            end_local=item["end_local"],
            start_offset=item["start_offset"],
            end_offset=item["end_offset"],
            timezone=item["timezone"],
            role_id=item["role"].id if item["role"] else None,
            station_id=item["station"].id if item["station"] else None,
            shift_id=item["shift"].id if item["shift"] else None,
            labels=item["labels"],
        )
        DescansoPublicado.objects.bulk_create(
            [
                DescansoPublicado(
                    organization_id=period.organization_id,
                    publication=publication,
                    assignment_id=item["assignment_id"],
                    break_id=row["break_id"],
                    starts_at=row["starts_at"],
                    ends_at=row["ends_at"],
                    start_local=row["start_local"],
                    end_local=row["end_local"],
                    start_offset=row["start_offset"],
                    end_offset=row["end_offset"],
                )
                for row in item["breaks"]
            ]
        )


def publish_period(actor, period_id, expected_etag):
    initial_period = _load_period_for_actor(actor, period_id)
    with organization_lock(actor.organization_id):
        period = _load_period_for_actor(actor, initial_period.id)
        authorize_planner(actor, period.branch_id)
        require_matching_etag(period, expected_etag)
        validation_time = timezone.now()
        ineligible_fields = []
        for index, row in enumerate(period.draft.assignments.order_by("starts_at", "assignment_id")):
            if row.starts_at <= validation_time:
                continue
            eligible = row.employee.active and HabilitacionSucursal.objects.filter(
                organization_id=period.organization_id,
                branch_id=period.branch_id,
                employee_id=row.employee_id,
                enabled=True,
            ).exists()
            if not eligible:
                ineligible_fields.append(
                    {"path": f"assignments[{index}].employee_id", "code": "employee_ineligible_future"}
                )
        if ineligible_fields:
            raise EmployeeIneligibleFuture(ineligible_fields)
        candidate = validate_draft_payload(period, _draft_payload(period.draft))
        validate_candidate_conflicts(actor, period, candidate)
        assignments = canonical_candidate(candidate)
        roster = _roster(period, candidate)
        canonical_roster = [
            {"employee_id": str(employee.id), "employee_label": employee.display_name}
            for employee in roster
        ]
        content_hash = _content_hash(assignments, canonical_roster)
        previous = None
        if period.current_publication_id:
            previous = PublicacionProgramacion.objects.get(
                pk=period.current_publication_id, period=period
            )
            if previous.content_hash == content_hash:
                return {
                    "outcome": "no_changes",
                    "publication": previous,
                    "publication_id": previous.id,
                    "version": previous.version,
                    "previous_version": previous.version - 1 or None,
                    "published_at": previous.published_at,
                    "changes": [],
                    "etag": make_period_etag(period),
                }

        previous_assignments = canonical_publication(previous) if previous else []
        previous_roster = canonical_publication_roster(previous) if previous else []
        changes = (
            build_publication_changes(
                previous_assignments, assignments, previous_roster, canonical_roster
            )
            if previous
            else []
        )
        version = previous.version + 1 if previous else 1
        correlation_id = uuid.uuid4()
        user = get_user_model().objects.get(pk=actor.user_id)
        with transaction.atomic():
            publication = PublicacionProgramacion.objects.create(
                organization_id=period.organization_id,
                period=period,
                version=version,
                previous_publication_id=previous.id if previous else None,
                published_by_id=actor.user_id,
                publisher_label=_publisher_label(user),
                content_hash=content_hash,
                branch_label=period.branch.name,
                date_from=period.date_from,
                date_to=period.date_to,
                timezone=period.timezone,
            )
            _create_snapshot(period, publication, candidate, roster)
            change_rows = [
                CambioPublicacion.objects.create(
                    organization_id=period.organization_id,
                    publication=publication,
                    assignment_id=item["assignment_id"],
                    employee_id=item["employee_id"],
                    kind=item["kind"],
                    before=item["before"],
                    after=item["after"],
                    changed_fields=item["changed_fields"],
                )
                for item in changes
            ]
            _before_publication_pointer(period, publication)
            period.current_publication_id = publication.id
            period.edit_revision += 1
            period.save(update_fields=["current_publication_id", "edit_revision"])
            draft = period.draft
            draft.base_publication_id = publication.id
            draft.active = False
            draft.updated_by_id = actor.user_id
            draft.save(update_fields=["base_publication_id", "active", "updated_by", "updated_at"])
            event = Evento.objects.create(
                organization_id=period.organization_id,
                branch_id=period.branch_id,
                actor_id=actor.user_id,
                type="scheduling.period_published",
                subject_id=period.id,
                payload={
                    "period_id": str(period.id),
                    "publication_id": str(publication.id),
                    "version": version,
                    "previous_publication_id": str(previous.id) if previous else None,
                    "change_ids": [str(row.id) for row in change_rows],
                },
                correlation_id=correlation_id,
            )
            resolve_incidents_after_publication(period, event)
            Auditoria.objects.create(
                organization_id=period.organization_id,
                branch_id=period.branch_id,
                actor_id=actor.user_id,
                operation="scheduling.period.publish",
                subject_id=period.id,
                before=(
                    {"publication_id": str(previous.id), "version": previous.version}
                    if previous
                    else None
                ),
                after={
                    "publication_id": str(publication.id),
                    "version": version,
                    "content_hash": content_hash,
                    "roster_count": len(roster),
                    "assignment_count": len(candidate),
                },
                correlation_id=correlation_id,
            )
        return {
            "outcome": "published",
            "publication": publication,
            "publication_id": publication.id,
            "version": version,
            "previous_version": previous.version if previous else None,
            "published_at": publication.published_at,
            "changes": changes,
            "event": event,
            "etag": make_period_etag(period),
        }
