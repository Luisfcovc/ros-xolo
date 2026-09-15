"""Synchronous lifecycle for private PNG/PDF schedule exports."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ros_xolo.core.models import Auditoria, Evento
from ros_xolo.core.services.authorization import authorize_planner
from ros_xolo.programacion.exports.payload import build_export_payload
from ros_xolo.programacion.exports.renderer import ExportRenderError, render_export
from ros_xolo.programacion.models import ExportacionProgramacion


class InvalidExportFormat(ValueError):
    code = "invalid_request"


class ExportExpired(ValueError):
    code = "export_expired"


class ExportUnavailable(ValueError):
    code = "export_failed"


def export_storage_root() -> Path:
    root = Path(settings.EXPORT_STORAGE_ROOT).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _storage_path(storage_key: str) -> Path:
    root = export_storage_root()
    candidate = (root / storage_key).resolve()
    if candidate != root and root not in candidate.parents:
        raise ExportUnavailable("Clave de almacenamiento privada inválida.")
    return candidate


def _record_outcome(export, *, event_type, operation, before=None, after=None):
    correlation_id = uuid.uuid4()
    Evento.objects.create(
        organization_id=export.organization_id,
        branch_id=export.branch_id,
        actor_id=export.requested_by_id,
        type=event_type,
        subject_id=export.id,
        payload={
            "export_id": str(export.id),
            "period_id": str(export.period_id),
            "format": export.format,
            "status": export.status,
            "error_code": export.error_code,
        },
        correlation_id=correlation_id,
    )
    Auditoria.objects.create(
        organization_id=export.organization_id,
        branch_id=export.branch_id,
        actor_id=export.requested_by_id,
        operation=operation,
        subject_id=export.id,
        before=before,
        after=after,
        outcome="success" if export.status == ExportacionProgramacion.READY else "failed",
        correlation_id=correlation_id,
    )


def request_export(actor, period_id, export_format):
    """Freeze quickly, render outside all database locks, and publish metadata atomically."""

    if export_format not in {ExportacionProgramacion.PNG, ExportacionProgramacion.PDF}:
        raise InvalidExportFormat("format debe ser png o pdf.")

    frozen = build_export_payload(actor, period_id)
    payload = frozen.to_dict()
    period = payload["period"]
    export = ExportacionProgramacion.objects.create(
        organization_id=actor.organization_id,
        branch_id=period["branch_id"],
        period_id=period["id"],
        requested_by_id=actor.user_id,
        format=export_format,
        manifest=frozen.manifest_dict(),
        expected_counts=frozen.counts_dict(),
        pending_draft_excluded=payload["pending_draft_excluded"],
    )
    storage_key = f"{export.organization_id}/{export.id}.{export_format}"
    destination = _storage_path(storage_key)
    started = time.monotonic()
    try:
        result = render_export(frozen, export_format, destination)
        duration_ms = max(0, round((time.monotonic() - started) * 1000))
        with transaction.atomic():
            export = ExportacionProgramacion.objects.select_for_update().get(pk=export.id)
            export.status = ExportacionProgramacion.READY
            export.generated_at = timezone.now()
            export.content_hash = result.sha256
            export.private_storage_key = storage_key
            export.byte_size = result.byte_size
            export.duration_ms = duration_ms
            export.error_code = None
            export.save(
                update_fields=[
                    "status", "generated_at", "content_hash", "private_storage_key",
                    "byte_size", "duration_ms", "error_code",
                ]
            )
            _record_outcome(
                export,
                event_type="scheduling.export_ready",
                operation="scheduling.export.generate",
                before={"status": ExportacionProgramacion.GENERATING},
                after={
                    "status": export.status,
                    "sha256": export.content_hash,
                    "byte_size": export.byte_size,
                    "duration_ms": export.duration_ms,
                },
            )
    except Exception as exc:
        destination.unlink(missing_ok=True)
        duration_ms = max(0, round((time.monotonic() - started) * 1000))
        error_code = getattr(exc, "code", "export_failed")
        with transaction.atomic():
            export = ExportacionProgramacion.objects.select_for_update().get(pk=export.id)
            export.status = ExportacionProgramacion.FAILED
            export.generated_at = timezone.now()
            export.duration_ms = duration_ms
            export.error_code = error_code
            export.content_hash = None
            export.private_storage_key = None
            export.byte_size = None
            export.save(
                update_fields=[
                    "status", "generated_at", "duration_ms", "error_code",
                    "content_hash", "private_storage_key", "byte_size",
                ]
            )
            _record_outcome(
                export,
                event_type="scheduling.export_failed",
                operation="scheduling.export.generate",
                before={"status": ExportacionProgramacion.GENERATING},
                after={"status": export.status, "error_code": error_code, "duration_ms": duration_ms},
            )
        if isinstance(exc, ExportRenderError):
            raise
        raise ExportRenderError("No se pudo generar la exportación.") from exc

    # A permission revoked while Chromium was running prevents delivery even
    # though the private, already-frozen artifact may have completed.
    authorize_planner(actor, export.branch_id)
    return export


def _expire_if_needed(export, *, now=None):
    now = now or timezone.now()
    if export.status != ExportacionProgramacion.EXPIRED and export.expires_at <= now:
        if export.private_storage_key:
            _storage_path(export.private_storage_key).unlink(missing_ok=True)
        export.status = ExportacionProgramacion.EXPIRED
        export.private_storage_key = None
        export.save(update_fields=["status", "private_storage_key"])
    return export


def get_export(actor, export_id):
    export = ExportacionProgramacion.objects.select_related("period").get(
        pk=export_id,
        organization_id=actor.organization_id,
    )
    authorize_planner(actor, export.branch_id)
    return _expire_if_needed(export)


def export_metadata(export):
    download_url = None
    if export.status == ExportacionProgramacion.READY:
        download_url = f"/api/v1/planning/exports/{export.id}/file"
    return {
        "export_id": str(export.id),
        "format": export.format,
        "status": export.status,
        "manifest": export.manifest,
        "expected_counts": export.expected_counts,
        "generated_at": export.generated_at.isoformat() if export.generated_at else None,
        "expires_at": export.expires_at.isoformat(),
        "sha256": export.content_hash,
        "byte_size": export.byte_size,
        "duration_ms": export.duration_ms,
        "download_url": download_url,
        "pending_draft_excluded": export.pending_draft_excluded,
        "error_code": export.error_code if export.status == ExportacionProgramacion.FAILED else None,
    }


def get_export_file(actor, export_id):
    export = get_export(actor, export_id)
    if export.status == ExportacionProgramacion.EXPIRED:
        raise ExportExpired("La exportación venció.")
    if export.status != ExportacionProgramacion.READY or not export.private_storage_key:
        raise ExportUnavailable("La exportación no está disponible.")
    path = _storage_path(export.private_storage_key)
    if not path.is_file() or path.stat().st_size != export.byte_size:
        raise ExportUnavailable("El archivo privado no está disponible.")
    return export, path


def purge_expired_exports(*, now=None):
    now = now or timezone.now()
    expired_count = 0
    for export in ExportacionProgramacion.objects.filter(expires_at__lte=now).exclude(
        status=ExportacionProgramacion.EXPIRED
    ).iterator():
        _expire_if_needed(export, now=now)
        expired_count += 1

    temporary_count = 0
    cutoff = now - timedelta(hours=1)
    for path in export_storage_root().rglob("*.tmp"):
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.get_current_timezone())
            if modified <= cutoff:
                path.unlink(missing_ok=True)
                temporary_count += 1
        except FileNotFoundError:
            pass
    return {"expired": expired_count, "temporaries_removed": temporary_count}
