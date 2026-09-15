import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from ros_xolo.core.models import Asignacion, Empleado, Organizacion
from .drafts import PeriodoProgramacion


class PublicationModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organizacion, on_delete=models.PROTECT)
    class Meta: abstract = True


class PublicacionProgramacion(PublicationModel):
    period = models.ForeignKey(PeriodoProgramacion, on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    previous_publication_id = models.UUIDField(null=True, blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    publisher_label = models.CharField(max_length=200)
    published_at = models.DateTimeField(auto_now_add=True)
    content_hash = models.CharField(max_length=64)
    branch_label = models.CharField(max_length=200)
    date_from = models.DateField()
    date_to = models.DateField()
    timezone = models.CharField(max_length=64)
    class Meta: constraints = [models.UniqueConstraint(fields=["period", "version"], name="schedule_publication_version_uniq")]


class FilaEmpleadoPublicada(PublicationModel):
    publication = models.ForeignKey(PublicacionProgramacion, on_delete=models.PROTECT, related_name="roster")
    employee = models.ForeignKey(Empleado, on_delete=models.PROTECT)
    employee_label = models.CharField(max_length=200)
    display_order = models.PositiveIntegerField()
    class Meta: constraints = [models.UniqueConstraint(fields=["publication", "employee"], name="schedule_publication_employee_uniq")]


class JornadaPublicada(PublicationModel):
    publication = models.ForeignKey(PublicacionProgramacion, on_delete=models.PROTECT, related_name="assignments")
    assignment = models.ForeignKey(Asignacion, on_delete=models.PROTECT)
    employee = models.ForeignKey(Empleado, on_delete=models.PROTECT)
    branch_id = models.UUIDField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    start_local = models.DateTimeField()
    end_local = models.DateTimeField()
    start_offset = models.IntegerField()
    end_offset = models.IntegerField()
    timezone = models.CharField(max_length=64)
    role_id = models.UUIDField(null=True, blank=True)
    station_id = models.UUIDField(null=True, blank=True)
    shift_id = models.UUIDField(null=True, blank=True)
    labels = models.JSONField(default=dict)
    class Meta: constraints = [models.UniqueConstraint(fields=["publication", "assignment"], name="schedule_snapshot_assignment_uniq")]


class DescansoPublicado(PublicationModel):
    publication = models.ForeignKey(PublicacionProgramacion, on_delete=models.PROTECT, related_name="breaks")
    assignment = models.ForeignKey(Asignacion, on_delete=models.PROTECT)
    break_id = models.UUIDField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    start_local = models.DateTimeField()
    end_local = models.DateTimeField()
    start_offset = models.IntegerField()
    end_offset = models.IntegerField()
    class Meta: constraints = [models.UniqueConstraint(fields=["publication", "break_id"], name="schedule_snapshot_break_uniq")]


class CambioPublicacion(PublicationModel):
    ASSIGNMENT_ADDED = "assignment_added"
    ASSIGNMENT_MODIFIED = "assignment_modified"
    ASSIGNMENT_REMOVED = "assignment_removed"
    ROSTER_ADDED = "roster_added"
    ROSTER_REMOVED = "roster_removed"
    ROSTER_MODIFIED = "roster_modified"
    KIND_CHOICES = [
        (ASSIGNMENT_ADDED, "Jornada añadida"),
        (ASSIGNMENT_MODIFIED, "Jornada modificada"),
        (ASSIGNMENT_REMOVED, "Jornada retirada"),
        (ROSTER_ADDED, "Fila añadida"),
        (ROSTER_REMOVED, "Fila retirada"),
        (ROSTER_MODIFIED, "Fila modificada"),
    ]

    publication = models.ForeignKey(
        PublicacionProgramacion, on_delete=models.PROTECT, related_name="changes"
    )
    assignment = models.ForeignKey(
        Asignacion, null=True, blank=True, on_delete=models.PROTECT
    )
    employee = models.ForeignKey(
        Empleado, null=True, blank=True, on_delete=models.PROTECT
    )
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    changed_fields = models.JSONField(default=list)

    class Meta:
        indexes = [
            models.Index(
                fields=["publication", "kind", "id"],
                name="programacio_public_07cb0f_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(before__isnull=False) | models.Q(after__isnull=False),
                name="schedule_change_has_content",
            )
        ]

    def clean(self):
        super().clean()
        if self.publication_id and self.publication.organization_id != self.organization_id:
            raise ValidationError("Publicación fuera de organización.")
        if self.kind.endswith("added") and self.before is not None:
            raise ValidationError({"before": "Debe ser null para una alta."})
        if self.kind.endswith("removed") and self.after is not None:
            raise ValidationError({"after": "Debe ser null para un retiro."})
        if self.kind.endswith("modified") and (self.before is None or self.after is None):
            raise ValidationError("Una modificación requiere before y after.")

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Las diferencias publicadas son inmutables.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Las diferencias publicadas no se eliminan.")
