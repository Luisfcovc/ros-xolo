"""Private, metadata-only records for generated schedule exports."""

from __future__ import annotations

from datetime import timedelta
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from ros_xolo.core.models import Organizacion, Sucursal

from .drafts import PeriodoProgramacion


def default_expiration():
    """Keep a completed export available for the initial 24-hour retention window."""

    return timezone.now() + timedelta(hours=24)


class ExportacionProgramacion(models.Model):
    PNG = "png"
    PDF = "pdf"
    FORMATS = [(PNG, "PNG"), (PDF, "PDF")]

    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    EXPIRED = "expired"
    STATUSES = [
        (GENERATING, "Generando"),
        (READY, "Lista"),
        (FAILED, "Fallida"),
        (EXPIRED, "Vencida"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organizacion, on_delete=models.PROTECT)
    branch = models.ForeignKey(Sucursal, on_delete=models.PROTECT)
    period = models.ForeignKey(PeriodoProgramacion, on_delete=models.PROTECT)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    format = models.CharField(max_length=3, choices=FORMATS)
    status = models.CharField(max_length=10, choices=STATUSES, default=GENERATING)
    requested_at = models.DateTimeField(auto_now_add=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(default=default_expiration, db_index=True)
    manifest = models.JSONField(default=dict)
    expected_counts = models.JSONField(default=dict)
    content_hash = models.CharField(max_length=64, null=True, blank=True)
    private_storage_key = models.CharField(max_length=512, null=True, blank=True)
    byte_size = models.PositiveBigIntegerField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=64, null=True, blank=True)
    pending_draft_excluded = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "branch", "status"], name="schedule_export_status_idx"),
            models.Index(fields=["expires_at", "status"], name="schedule_export_expiry_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["generating", "ready", "failed", "expired"]),
                name="schedule_export_valid_status",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        ("status", "generating"),
                        ("content_hash__isnull", True),
                        ("private_storage_key__isnull", True),
                    )
                    | models.Q(
                        ("status", "ready"),
                        ("content_hash__isnull", False),
                        ("private_storage_key__isnull", False),
                    )
                    | models.Q(status__in=["failed", "expired"])
                ),
                name="schedule_export_state_metadata",
            ),
        ]

    def clean(self):
        super().clean()
        if self.branch_id and self.branch.organization_id != self.organization_id:
            raise ValidationError("Sucursal fuera de organización.")
        if self.period_id and (
            self.period.organization_id != self.organization_id
            or self.period.branch_id != self.branch_id
        ):
            raise ValidationError("Periodo fuera de sucursal u organización.")
