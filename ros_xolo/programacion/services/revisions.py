"""Semantic comparison and revision preparation for published schedules."""

from __future__ import annotations

from datetime import timezone as datetime_timezone

from django.db import transaction

from ros_xolo.core.services.authorization import authorize_planner
from ros_xolo.core.services.locking import organization_lock
from ros_xolo.programacion.models import (
    DescansoBorrador,
    JornadaBorrador,
    PeriodoProgramacion,
    PublicacionProgramacion,
)


ASSIGNMENT_FIELDS = (
    "employee_id",
    "starts_at",
    "ends_at",
    "start_offset",
    "end_offset",
    "timezone",
    "role_id",
    "station_id",
    "shift_id",
    "labels",
    "breaks",
)


def canonical_publication(publication):
    breaks = {}
    for row in publication.breaks.all():
        breaks.setdefault(str(row.assignment_id), []).append(
            {
                "break_id": str(row.break_id),
                "starts_at": row.starts_at.astimezone(datetime_timezone.utc).isoformat(),
                "ends_at": row.ends_at.astimezone(datetime_timezone.utc).isoformat(),
                "start_offset": row.start_offset,
                "end_offset": row.end_offset,
            }
        )
    assignments = []
    for row in publication.assignments.all():
        assignment_id = str(row.assignment_id)
        assignments.append(
            {
                "assignment_id": assignment_id,
                "employee_id": str(row.employee_id),
                "starts_at": row.starts_at.astimezone(datetime_timezone.utc).isoformat(),
                "ends_at": row.ends_at.astimezone(datetime_timezone.utc).isoformat(),
                "start_offset": row.start_offset,
                "end_offset": row.end_offset,
                "timezone": row.timezone,
                "role_id": str(row.role_id) if row.role_id else None,
                "station_id": str(row.station_id) if row.station_id else None,
                "shift_id": str(row.shift_id) if row.shift_id else None,
                "labels": row.labels,
                "breaks": sorted(
                    breaks.get(assignment_id, []), key=lambda item: item["break_id"]
                ),
            }
        )
    return sorted(assignments, key=lambda item: item["assignment_id"])


def canonical_publication_roster(publication):
    return sorted(
        [
            {
                "employee_id": str(row.employee_id),
                "employee_label": row.employee_label,
            }
            for row in publication.roster.all()
        ],
        key=lambda item: item["employee_id"],
    )


def _changes(before, after, fields):
    return [field for field in fields if before.get(field) != after.get(field)]


def build_publication_changes(
    before_assignments, after_assignments, before_roster, after_roster
):
    """Compare only semantic fields, returning a deterministic change list."""

    before_by_id = {item["assignment_id"]: item for item in before_assignments}
    after_by_id = {item["assignment_id"]: item for item in after_assignments}
    before_roster_by_id = {item["employee_id"]: item for item in before_roster}
    after_roster_by_id = {item["employee_id"]: item for item in after_roster}
    changes = []

    for identifier in sorted(after_by_id.keys() - before_by_id.keys()):
        after = after_by_id[identifier]
        changes.append(
            {
                "kind": "assignment_added",
                "assignment_id": identifier,
                "employee_id": after["employee_id"],
                "before": None,
                "after": after,
                "changed_fields": list(ASSIGNMENT_FIELDS),
            }
        )
    for identifier in sorted(after_by_id.keys() & before_by_id.keys()):
        before, after = before_by_id[identifier], after_by_id[identifier]
        changed_fields = _changes(before, after, ASSIGNMENT_FIELDS)
        if changed_fields:
            changes.append(
                {
                    "kind": "assignment_modified",
                    "assignment_id": identifier,
                    "employee_id": after["employee_id"],
                    "before": before,
                    "after": after,
                    "changed_fields": changed_fields,
                }
            )
    for identifier in sorted(before_by_id.keys() - after_by_id.keys()):
        before = before_by_id[identifier]
        changes.append(
            {
                "kind": "assignment_removed",
                "assignment_id": identifier,
                "employee_id": before["employee_id"],
                "before": before,
                "after": None,
                "changed_fields": list(ASSIGNMENT_FIELDS),
            }
        )

    for identifier in sorted(after_roster_by_id.keys() - before_roster_by_id.keys()):
        after = after_roster_by_id[identifier]
        changes.append(
            {
                "kind": "roster_added",
                "assignment_id": None,
                "employee_id": identifier,
                "before": None,
                "after": after,
                "changed_fields": ["employee_label"],
            }
        )
    for identifier in sorted(after_roster_by_id.keys() & before_roster_by_id.keys()):
        before, after = before_roster_by_id[identifier], after_roster_by_id[identifier]
        changed_fields = _changes(before, after, ("employee_label",))
        if changed_fields:
            changes.append(
                {
                    "kind": "roster_modified",
                    "assignment_id": None,
                    "employee_id": identifier,
                    "before": before,
                    "after": after,
                    "changed_fields": changed_fields,
                }
            )
    for identifier in sorted(before_roster_by_id.keys() - after_roster_by_id.keys()):
        before = before_roster_by_id[identifier]
        changes.append(
            {
                "kind": "roster_removed",
                "assignment_id": None,
                "employee_id": identifier,
                "before": before,
                "after": None,
                "changed_fields": ["employee_label"],
            }
        )
    return changes


def open_revision(actor, period_id):
    """Open the work draft on the current publication without mutating history."""

    with organization_lock(actor.organization_id):
        period = PeriodoProgramacion.objects.select_related("draft").get(
            pk=period_id, organization_id=actor.organization_id
        )
        authorize_planner(actor, period.branch_id)
        if period.current_publication_id is None:
            return period.draft
        draft = period.draft
        if draft.base_publication_id == period.current_publication_id:
            return draft
        publication = PublicacionProgramacion.objects.get(
            pk=period.current_publication_id, period=period
        )
        with transaction.atomic():
            draft.breaks.all().delete()
            draft.assignments.all().delete()
            for row in publication.assignments.all():
                JornadaBorrador.objects.create(
                    organization_id=period.organization_id,
                    draft=draft,
                    assignment_id=row.assignment_id,
                    employee_id=row.employee_id,
                    branch_id=row.branch_id,
                    starts_at=row.starts_at,
                    ends_at=row.ends_at,
                    start_local=row.start_local,
                    end_local=row.end_local,
                    start_offset=row.start_offset,
                    end_offset=row.end_offset,
                    timezone=row.timezone,
                    role_id=row.role_id,
                    station_id=row.station_id,
                    shift_id=row.shift_id,
                    labels=row.labels,
                )
            for row in publication.breaks.all():
                DescansoBorrador.objects.create(
                    id=row.break_id,
                    organization_id=period.organization_id,
                    draft=draft,
                    assignment_id=row.assignment_id,
                    starts_at=row.starts_at,
                    ends_at=row.ends_at,
                    start_local=row.start_local,
                    end_local=row.end_local,
                    start_offset=row.start_offset,
                    end_offset=row.end_offset,
                )
            draft.base_publication_id = publication.id
            draft.active = False
            draft.updated_by_id = actor.user_id
            draft.save(update_fields=["base_publication_id", "active", "updated_by", "updated_at"])
        return draft
