"""Validation and canonicalization for complete schedule draft replacements.

This module deliberately performs no writes.  Services can therefore validate the
whole candidate before replacing any part of the persisted draft.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as datetime_timezone
from typing import Any

from ros_xolo.core.models import (
    Asignacion,
    Empleado,
    Estacion,
    HabilitacionSucursal,
    Rol,
    Turno,
)
from ros_xolo.programacion.models import (
    AsignacionJornada,
    DescansoBorrador,
    DescansoPublicado,
)
from ros_xolo.programacion.services.time import LocalTimeError, parse_period_datetime


ASSIGNMENT_FIELDS = {
    "assignment_id",
    "employee_id",
    "starts_at",
    "ends_at",
    "role_id",
    "station_id",
    "shift_id",
    "breaks",
}
BREAK_FIELDS = {"break_id", "starts_at", "ends_at"}


class ScheduleValidationError(ValueError):
    """A client-correctable validation error with field-level context."""

    def __init__(self, message: str, *, code: str = "invalid_reference", fields=None):
        super().__init__(message)
        self.code = code
        self.fields = fields or []


def _field_error(path: str, code: str, message: str):
    raise ScheduleValidationError(
        message,
        code=code,
        fields=[{"path": path, "code": code}],
    )


def _uuid(value: Any, path: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ScheduleValidationError(
            f"{path} debe ser un UUID válido.",
            code="invalid_reference",
            fields=[{"path": path, "code": "invalid_reference"}],
        ) from exc


def _optional_uuid(value: Any, path: str) -> uuid.UUID | None:
    return None if value is None else _uuid(value, path)


def _reference(model, reference_id, *, period, path, branch_scoped=False):
    if reference_id is None:
        return None
    filters = {
        "pk": reference_id,
        "organization_id": period.organization_id,
        "active": True,
    }
    if branch_scoped:
        filters["branch_id"] = period.branch_id
    try:
        return model.objects.get(**filters)
    except model.DoesNotExist as exc:
        raise ScheduleValidationError(
            "Referencia inexistente, inactiva o fuera del ámbito.",
            code="invalid_reference",
            fields=[{"path": path, "code": "invalid_reference"}],
        ) from exc


def _applicable_reference(model, reference_id, *, period, path):
    reference = _reference(model, reference_id, period=period, path=path)
    if not reference.applicable_branches.filter(pk=period.branch_id).exists():
        _field_error(path, "invalid_reference", "La referencia no aplica a la sucursal.")
    return reference


def _parse_in_period(value: Any, *, period, path: str):
    try:
        return parse_period_datetime(value, period.timezone)
    except (LocalTimeError, TypeError, ValueError) as exc:
        message = str(exc)
        lowered = message.lower()
        if "ambigu" in lowered:
            code = "ambiguous_local_time"
        elif "inexist" in lowered:
            code = "nonexistent_local_time"
        else:
            code = "invalid_interval"
        raise ScheduleValidationError(
            message,
            code=code,
            fields=[{"path": path, "code": code}],
        ) from exc


def _validate_assignment_identity(assignment_id, *, period, path):
    link = (
        AsignacionJornada.objects.select_related("assignment", "period")
        .filter(assignment_id=assignment_id)
        .first()
    )
    if link:
        if (
            link.organization_id != period.organization_id
            or link.period_id != period.id
            or link.assignment.organization_id != period.organization_id
            or link.assignment.kind != "jornada"
        ):
            _field_error(path, "invalid_reference", "La asignación pertenece a otro periodo.")
        return link.assignment

    if Asignacion.objects.filter(pk=assignment_id).exists():
        _field_error(path, "invalid_reference", "El ID ya pertenece a otra asignación.")
    return None


def _validate_break_identity(break_id, assignment_id, *, period, path):
    draft_break = DescansoBorrador.objects.filter(pk=break_id).first()
    if draft_break and (
        draft_break.organization_id != period.organization_id
        or draft_break.assignment_id != assignment_id
        or draft_break.draft.period_id != period.id
    ):
        _field_error(path, "invalid_reference", "El descanso pertenece a otra jornada.")

    published_breaks = DescansoPublicado.objects.filter(break_id=break_id)
    if published_breaks.exclude(
        organization_id=period.organization_id,
        assignment_id=assignment_id,
        publication__period_id=period.id,
    ).exists():
        _field_error(path, "invalid_reference", "El descanso pertenece a otra jornada.")


def validate_draft_payload(period, payload: Any) -> list[dict[str, Any]]:
    """Validate a complete replacement and return a normalized candidate.

    ``payload`` may be the HTTP-shaped ``{"assignments": [...]}`` object or the
    assignments list used by the internal service contract.
    """

    if isinstance(payload, dict):
        unknown = set(payload) - {"assignments"}
        if unknown:
            _field_error(sorted(unknown)[0], "invalid_request", "Campo desconocido.")
        if "assignments" not in payload:
            _field_error("assignments", "invalid_request", "assignments es obligatorio.")
        payload = payload["assignments"]
    if not isinstance(payload, list):
        _field_error("assignments", "invalid_request", "assignments debe ser una lista.")

    normalized = []
    seen_assignments: set[uuid.UUID] = set()
    seen_breaks: set[uuid.UUID] = set()

    for index, item in enumerate(payload):
        base = f"assignments[{index}]"
        if not isinstance(item, dict):
            _field_error(base, "invalid_request", "Cada jornada debe ser un objeto.")
        unknown = set(item) - ASSIGNMENT_FIELDS
        if unknown:
            _field_error(f"{base}.{sorted(unknown)[0]}", "invalid_request", "Campo desconocido.")
        required = {"assignment_id", "employee_id", "starts_at", "ends_at", "breaks"}
        missing = sorted(required - set(item))
        if missing:
            _field_error(f"{base}.{missing[0]}", "invalid_request", "Campo obligatorio.")

        assignment_id = _uuid(item["assignment_id"], f"{base}.assignment_id")
        if assignment_id in seen_assignments:
            _field_error(
                f"{base}.assignment_id",
                "invalid_reference",
                "assignment_id está duplicado.",
            )
        seen_assignments.add(assignment_id)
        existing_assignment = _validate_assignment_identity(
            assignment_id,
            period=period,
            path=f"{base}.assignment_id",
        )

        employee_id = _uuid(item["employee_id"], f"{base}.employee_id")
        employee = _reference(
            Empleado,
            employee_id,
            period=period,
            path=f"{base}.employee_id",
        )
        if not HabilitacionSucursal.objects.filter(
            organization_id=period.organization_id,
            branch_id=period.branch_id,
            employee_id=employee.id,
            enabled=True,
        ).exists():
            _field_error(
                f"{base}.employee_id",
                "invalid_reference",
                "El empleado no está habilitado en la sucursal.",
            )

        role_id = _optional_uuid(item.get("role_id"), f"{base}.role_id")
        station_id = _optional_uuid(item.get("station_id"), f"{base}.station_id")
        shift_id = _optional_uuid(item.get("shift_id"), f"{base}.shift_id")
        if role_id is None and station_id is None:
            _field_error(
                f"{base}.role_id",
                "invalid_reference",
                "Se requiere rol o estación.",
            )
        role = (
            _applicable_reference(
                Rol,
                role_id,
                period=period,
                path=f"{base}.role_id",
            )
            if role_id
            else None
        )
        station = (
            _reference(
                Estacion,
                station_id,
                period=period,
                path=f"{base}.station_id",
                branch_scoped=True,
            )
            if station_id
            else None
        )
        if station and (
            station.area.organization_id != period.organization_id
            or station.area.branch_id != period.branch_id
        ):
            _field_error(
                f"{base}.station_id",
                "invalid_reference",
                "El área de la estación no pertenece a la sucursal.",
            )
        shift = (
            _applicable_reference(
                Turno,
                shift_id,
                period=period,
                path=f"{base}.shift_id",
            )
            if shift_id
            else None
        )

        start = _parse_in_period(item["starts_at"], period=period, path=f"{base}.starts_at")
        end = _parse_in_period(item["ends_at"], period=period, path=f"{base}.ends_at")
        if end["utc"] <= start["utc"]:
            _field_error(
                f"{base}.ends_at",
                "invalid_interval",
                "El fin debe ser posterior al inicio.",
            )
        if not (period.date_from <= start["local"].date() <= period.date_to):
            _field_error(
                f"{base}.starts_at",
                "invalid_interval",
                "La fecha local de inicio está fuera del periodo.",
            )

        breaks_payload = item["breaks"]
        if not isinstance(breaks_payload, list):
            _field_error(f"{base}.breaks", "invalid_request", "breaks debe ser una lista.")
        normalized_breaks = []
        for break_index, break_item in enumerate(breaks_payload):
            break_base = f"{base}.breaks[{break_index}]"
            if not isinstance(break_item, dict):
                _field_error(break_base, "invalid_request", "Cada descanso debe ser un objeto.")
            unknown = set(break_item) - BREAK_FIELDS
            if unknown:
                _field_error(
                    f"{break_base}.{sorted(unknown)[0]}",
                    "invalid_request",
                    "Campo desconocido.",
                )
            missing = sorted(BREAK_FIELDS - set(break_item))
            if missing:
                _field_error(f"{break_base}.{missing[0]}", "invalid_request", "Campo obligatorio.")
            break_id = _uuid(break_item["break_id"], f"{break_base}.break_id")
            if break_id in seen_breaks:
                _field_error(
                    f"{break_base}.break_id",
                    "invalid_reference",
                    "break_id está duplicado.",
                )
            seen_breaks.add(break_id)
            _validate_break_identity(
                break_id,
                assignment_id,
                period=period,
                path=f"{break_base}.break_id",
            )
            break_start = _parse_in_period(
                break_item["starts_at"],
                period=period,
                path=f"{break_base}.starts_at",
            )
            break_end = _parse_in_period(
                break_item["ends_at"],
                period=period,
                path=f"{break_base}.ends_at",
            )
            if break_end["utc"] <= break_start["utc"]:
                _field_error(
                    f"{break_base}.ends_at",
                    "invalid_break",
                    "El descanso debe tener duración positiva.",
                )
            if break_start["utc"] < start["utc"] or break_end["utc"] > end["utc"]:
                _field_error(
                    f"{break_base}.starts_at",
                    "invalid_break",
                    "El descanso debe estar contenido en la jornada.",
                )
            normalized_breaks.append(
                {
                    "break_id": break_id,
                    "starts_at": break_start["utc"],
                    "ends_at": break_end["utc"],
                    "start_local": break_start["local"],
                    "end_local": break_end["local"],
                    "start_offset": break_start["offset"],
                    "end_offset": break_end["offset"],
                }
            )

        ordered_breaks = sorted(
            normalized_breaks,
            key=lambda row: (row["starts_at"], row["ends_at"]),
        )
        for previous, current in zip(ordered_breaks, ordered_breaks[1:]):
            if current["starts_at"] < previous["ends_at"]:
                _field_error(
                    f"{base}.breaks",
                    "invalid_break",
                    "Los descansos no pueden superponerse.",
                )

        normalized.append(
            {
                "assignment_id": assignment_id,
                "existing_assignment": existing_assignment,
                "employee": employee,
                "branch": period.branch,
                "starts_at": start["utc"],
                "ends_at": end["utc"],
                "start_local": start["local"],
                "end_local": end["local"],
                "start_offset": start["offset"],
                "end_offset": end["offset"],
                "timezone": period.timezone,
                "role": role,
                "station": station,
                "shift": shift,
                "labels": {
                    "employee": employee.display_name,
                    "branch": period.branch.name,
                    "role": role.name if role else None,
                    "station": station.name if station else None,
                    "shift": shift.name if shift else None,
                },
                "breaks": normalized_breaks,
            }
        )

    return normalized


def canonical_candidate(candidate: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the stable, JSON-compatible semantic content of a candidate."""

    return sorted(
        [
            {
                "assignment_id": str(item["assignment_id"]),
                "employee_id": str(item["employee"].id),
                "starts_at": item["starts_at"].astimezone(datetime_timezone.utc).isoformat(),
                "ends_at": item["ends_at"].astimezone(datetime_timezone.utc).isoformat(),
                "start_offset": item["start_offset"],
                "end_offset": item["end_offset"],
                "timezone": item["timezone"],
                "role_id": str(item["role"].id) if item["role"] else None,
                "station_id": str(item["station"].id) if item["station"] else None,
                "shift_id": str(item["shift"].id) if item["shift"] else None,
                "labels": item["labels"],
                "breaks": sorted(
                    [
                        {
                            "break_id": str(row["break_id"]),
                            "starts_at": row["starts_at"]
                            .astimezone(datetime_timezone.utc)
                            .isoformat(),
                            "ends_at": row["ends_at"]
                            .astimezone(datetime_timezone.utc)
                            .isoformat(),
                            "start_offset": row["start_offset"],
                            "end_offset": row["end_offset"],
                        }
                        for row in item["breaks"]
                    ],
                    key=lambda row: row["break_id"],
                ),
            }
            for item in candidate
        ],
        key=lambda row: row["assignment_id"],
    )


def canonical_draft(draft) -> list[dict[str, Any]]:
    rows = []
    assignments = draft.assignments.select_related(
        "employee", "branch", "role", "station", "shift"
    )
    breaks_by_assignment = {}
    for break_row in draft.breaks.all():
        breaks_by_assignment.setdefault(break_row.assignment_id, []).append(
            {
                "break_id": str(break_row.id),
                "starts_at": break_row.starts_at.astimezone(datetime_timezone.utc).isoformat(),
                "ends_at": break_row.ends_at.astimezone(datetime_timezone.utc).isoformat(),
                "start_offset": break_row.start_offset,
                "end_offset": break_row.end_offset,
            }
        )
    for row in assignments:
        rows.append(
            {
                "assignment_id": str(row.assignment_id),
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
                    breaks_by_assignment.get(row.assignment_id, []),
                    key=lambda item: item["break_id"],
                ),
            }
        )
    return sorted(rows, key=lambda item: item["assignment_id"])
