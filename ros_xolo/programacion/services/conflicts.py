"""Conflict detection for complete schedule candidates.

Intervals are absolute and half-open.  The caller must hold the organization
mutex so the database state examined here cannot change before its write commits.
"""

from __future__ import annotations

from collections import defaultdict

from ros_xolo.core.models import PermisoPlaneacion
from ros_xolo.programacion.models import (
    JornadaBorrador,
    JornadaPublicada,
    PeriodoProgramacion,
)


def intervals_overlap(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


class OverlapConflict(ValueError):
    code = "overlap"
    action = "Corrige el horario o coordina con un planeador autorizado."

    def __init__(self, *, fields=None, conflicts=None):
        super().__init__("La jornada coincide con otra asignación.")
        self.fields = fields or []
        self.conflicts = conflicts or []


def _detail(actor, row, scope):
    allowed = PermisoPlaneacion.objects.filter(
        organization_id=actor.organization_id,
        user_id=actor.user_id,
        branch_id=row.branch_id,
        enabled=True,
    ).exists()
    if not allowed:
        return {"restricted": True, "scope": scope}
    return {
        "restricted": False,
        "scope": scope,
        "assignment_id": str(row.assignment_id),
        "branch_id": str(row.branch_id),
        "employee_id": str(row.employee_id),
        "starts_at": row.starts_at.isoformat(),
        "ends_at": row.ends_at.isoformat(),
    }


def validate_candidate_conflicts(actor, period, candidate):
    """Raise :class:`OverlapConflict` when *candidate* reserves shared time."""

    conflicts = []
    fields = []
    by_employee = defaultdict(list)
    for index, item in enumerate(candidate):
        by_employee[item["employee"].id].append((index, item))

    for rows in by_employee.values():
        ordered = sorted(rows, key=lambda pair: (pair[1]["starts_at"], pair[1]["ends_at"]))
        for position, (left_index, left) in enumerate(ordered):
            for right_index, right in ordered[position + 1 :]:
                if right["starts_at"] >= left["ends_at"]:
                    break
                if intervals_overlap(
                    left["starts_at"], left["ends_at"], right["starts_at"], right["ends_at"]
                ):
                    fields.extend(
                        [
                            {"path": f"assignments[{left_index}].starts_at", "code": "overlap"},
                            {"path": f"assignments[{right_index}].starts_at", "code": "overlap"},
                        ]
                    )
                    conflicts.append(
                        {
                            "restricted": False,
                            "scope": "candidate",
                            "assignment_ids": [
                                str(left["assignment_id"]),
                                str(right["assignment_id"]),
                            ],
                        }
                    )

    current_publications = list(
        PeriodoProgramacion.objects.filter(
            organization_id=period.organization_id,
            current_publication_id__isnull=False,
        )
        .exclude(pk=period.id)
        .values_list("current_publication_id", flat=True)
    )
    active_drafts = list(
        PeriodoProgramacion.objects.filter(
            organization_id=period.organization_id,
            draft__active=True,
        )
        .exclude(pk=period.id)
        .values_list("draft__id", flat=True)
    )

    for index, item in enumerate(candidate):
        published = JornadaPublicada.objects.filter(
            organization_id=period.organization_id,
            publication_id__in=current_publications,
            employee_id=item["employee"].id,
            starts_at__lt=item["ends_at"],
            ends_at__gt=item["starts_at"],
        )
        drafts = JornadaBorrador.objects.filter(
            organization_id=period.organization_id,
            draft_id__in=active_drafts,
            employee_id=item["employee"].id,
            starts_at__lt=item["ends_at"],
            ends_at__gt=item["starts_at"],
        )
        for row in published:
            conflicts.append(_detail(actor, row, "published"))
        for row in drafts:
            conflicts.append(_detail(actor, row, "draft"))
        if published.exists() or drafts.exists():
            fields.append({"path": f"assignments[{index}].starts_at", "code": "overlap"})

    if conflicts:
        deduplicated_fields = list({item["path"]: item for item in fields}.values())
        raise OverlapConflict(fields=deduplicated_fields, conflicts=conflicts)
