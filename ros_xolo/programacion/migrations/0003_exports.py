import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models

import ros_xolo.programacion.models.exports


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("programacion", "0002_publication_changes"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExportacionProgramacion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("format", models.CharField(choices=[("png", "PNG"), ("pdf", "PDF")], max_length=3)),
                ("status", models.CharField(choices=[("generating", "Generando"), ("ready", "Lista"), ("failed", "Fallida"), ("expired", "Vencida")], default="generating", max_length=10)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("generated_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(db_index=True, default=ros_xolo.programacion.models.exports.default_expiration)),
                ("manifest", models.JSONField(default=dict)),
                ("expected_counts", models.JSONField(default=dict)),
                ("content_hash", models.CharField(blank=True, max_length=64, null=True)),
                ("private_storage_key", models.CharField(blank=True, max_length=512, null=True)),
                ("byte_size", models.PositiveBigIntegerField(blank=True, null=True)),
                ("duration_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("error_code", models.CharField(blank=True, max_length=64, null=True)),
                ("pending_draft_excluded", models.BooleanField(default=False)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.sucursal")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.organizacion")),
                ("period", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="programacion.periodoprogramacion")),
                ("requested_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(
            model_name="exportacionprogramacion",
            index=models.Index(fields=["organization", "branch", "status"], name="schedule_export_status_idx"),
        ),
        migrations.AddIndex(
            model_name="exportacionprogramacion",
            index=models.Index(fields=["expires_at", "status"], name="schedule_export_expiry_idx"),
        ),
        migrations.AddConstraint(
            model_name="exportacionprogramacion",
            constraint=models.CheckConstraint(condition=models.Q(("status__in", ["generating", "ready", "failed", "expired"])), name="schedule_export_valid_status"),
        ),
        migrations.AddConstraint(
            model_name="exportacionprogramacion",
            constraint=models.CheckConstraint(condition=models.Q(("status", "generating"), ("content_hash__isnull", True), ("private_storage_key__isnull", True)) | models.Q(("status", "ready"), ("content_hash__isnull", False), ("private_storage_key__isnull", False)) | models.Q(("status__in", ["failed", "expired"])), name="schedule_export_state_metadata"),
        ),
    ]
