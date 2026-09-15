"""Atomic complete-replacement operations for schedule drafts."""

from __future__ import annotations

import hashlib
import hmac
import json

from django.db import transaction

from ros_xolo.core.models import Asignacion, Auditoria, Evento
from ros_xolo.core.services.authorization import authorize_planner
from ros_xolo.core.services.locking import organization_lock
from ros_xolo.programacion.models import (
    AsignacionJornada,
    DescansoBorrador,
    JornadaBorrador,
    PeriodoProgramacion,
)
from ros_xolo.programacion.services.validation import (
    canonical_candidate,
    canonical_draft,
    validate_draft_payload,
)
from ros_xolo.programacion.services.conflicts import validate_candidate_conflicts


class PreconditionRequired(ValueError):
    code = "precondition_required"


class StaleBase(ValueError):
    code = "stale_base"

    def __init__(self, current_etag):
        super().__init__("stale_base")
        self.current_etag = current_etag


def make_period_etag(period) -> str:
    """Build an opaque ETag from every mutable base a planner must review."""

    material = json.dumps(
        {
            "period_id": str(period.id),
            "edit_revision": period.edit_revision,
            "current_publication_id": (
                str(period.current_publication_id) if period.current_publication_id else None
            ),
            "core_revision": period.organization.core_revision,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return f'"{hashlib.sha256(material).hexdigest()}"'


def require_matching_etag(period, expected_etag):
    if expected_etag is None or not str(expected_etag).strip():
        raise PreconditionRequired("precondition_required")
    current = make_period_etag(period)
    if not hmac.compare_digest(str(expected_etag).strip(), current):
        raise StaleBase(current)
    return current


def _load_period_for_actor(actor, period_id):
    period = PeriodoProgramacion.objects.select_related("organization", "branch", "draft").get(
        pk=period_id,
        organization_id=actor.organization_id,
    )
    authorize_planner(actor, period.branch_id)
    return period


def replace_draft(actor, period_id, expected_etag, assignments):
    """Validate and atomically replace all assignments in a period draft."""

    initial_period = _load_period_for_actor(actor, period_id)
    with organization_lock(actor.organization_id):
        period = _load_period_for_actor(actor, initial_period.id)
        authorize_planner(actor, period.branch_id)
        require_matching_etag(period, expected_etag)

        candidate = validate_draft_payload(period, assignments)
        validate_candidate_conflicts(actor, period, candidate)
        draft = period.draft
        before = canonical_draft(draft)
        after = canonical_candidate(candidate)
        if before == after:
            return {
                "draft": draft,
                "saved": False,
                "etag": make_period_etag(period),
                "has_pending_changes": draft.active or period.current_publication_id is None,
            }

        correlation_id = __import__("uuid").uuid4()
        with transaction.atomic():
            wanted_assignment_ids = {item["assignment_id"] for item in candidate}
            draft.breaks.exclude(assignment_id__in=wanted_assignment_ids).delete()
            draft.assignments.exclude(assignment_id__in=wanted_assignment_ids).delete()

            for item in candidate:
                assignment = item["existing_assignment"]
                if assignment is None:
                    assignment = Asignacion.objects.create(
                        id=item["assignment_id"],
                        organization_id=period.organization_id,
                        kind="jornada",
                        created_by_id=actor.user_id,
                    )
                    AsignacionJornada.objects.create(
                        organization_id=period.organization_id,
                        assignment=assignment,
                        period=period,
                    )

                JornadaBorrador.objects.update_or_create(
                    draft=draft,
                    assignment=assignment,
                    defaults={
                        "organization_id": period.organization_id,
                        "employee": item["employee"],
                        "branch": period.branch,
                        "starts_at": item["starts_at"],
                        "ends_at": item["ends_at"],
                        "start_local": item["starts_at"],
                        "end_local": item["ends_at"],
                        "start_offset": item["start_offset"],
                        "end_offset": item["end_offset"],
                        "timezone": item["timezone"],
                        "role": item["role"],
                        "station": item["station"],
                        "shift": item["shift"],
                        "labels": item["labels"],
                    },
                )

                wanted_break_ids = {row["break_id"] for row in item["breaks"]}
                draft.breaks.filter(assignment=assignment).exclude(id__in=wanted_break_ids).delete()
                for break_row in item["breaks"]:
                    DescansoBorrador.objects.update_or_create(
                        id=break_row["break_id"],
                        defaults={
                            "organization_id": period.organization_id,
                            "draft": draft,
                            "assignment": assignment,
                            "starts_at": break_row["starts_at"],
                            "ends_at": break_row["ends_at"],
                            "start_local": break_row["starts_at"],
                            "end_local": break_row["ends_at"],
                            "start_offset": break_row["start_offset"],
                            "end_offset": break_row["end_offset"],
                        },
                    )

            period.edit_revision += 1
            period.save(update_fields=["edit_revision"])
            draft.active = True
            draft.updated_by_id = actor.user_id
            draft.save(update_fields=["active", "updated_by", "updated_at"])

            event = Evento.objects.create(
                organization_id=period.organization_id,
                branch_id=period.branch_id,
                actor_id=actor.user_id,
                type="scheduling.draft_saved",
                subject_id=draft.id,
                payload={
                    "period_id": str(period.id),
                    "edit_revision": period.edit_revision,
                    "assignment_ids": sorted(str(value) for value in wanted_assignment_ids),
                },
                correlation_id=correlation_id,
            )
            Auditoria.objects.create(
                organization_id=period.organization_id,
                branch_id=period.branch_id,
                actor_id=actor.user_id,
                operation="scheduling.draft.replace",
                subject_id=draft.id,
                before={"assignments": before},
                after={"assignments": after},
                correlation_id=correlation_id,
            )

        return {
            "draft": draft,
            "event": event,
            "saved": True,
            "etag": make_period_etag(period),
            "has_pending_changes": True,
        }
