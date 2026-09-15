import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from ros_xolo.core.models import Asignacion, Empleado, Estacion, Organizacion, Rol, Sucursal, Turno


class UuidTenantModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organizacion, on_delete=models.PROTECT)
    class Meta: abstract = True


class PeriodoProgramacion(UuidTenantModel):
    branch = models.ForeignKey(Sucursal, on_delete=models.PROTECT)
    date_from = models.DateField()
    date_to = models.DateField()
    timezone = models.CharField(max_length=64)
    current_publication_id = models.UUIDField(null=True, blank=True)
    edit_revision = models.PositiveBigIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(date_to__gte=models.F("date_from")), name="schedule_period_dates_ordered")]
        indexes = [models.Index(fields=["organization", "branch", "date_from", "date_to"])]
    def clean(self):
        if self.date_from and self.date_to and self.date_to < self.date_from: raise ValidationError({"date_to": "No puede ser anterior a date_from."})
        if self.branch_id and self.branch.organization_id != self.organization_id: raise ValidationError("Sucursal fuera de organización.")


class BorradorProgramacion(UuidTenantModel):
    period = models.OneToOneField(PeriodoProgramacion, on_delete=models.PROTECT, related_name="draft")
    base_publication_id = models.UUIDField(null=True, blank=True)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    def clean(self):
        if self.period.organization_id != self.organization_id: raise ValidationError("Periodo fuera de organización.")


class AsignacionJornada(UuidTenantModel):
    assignment = models.OneToOneField(Asignacion, on_delete=models.PROTECT)
    period = models.ForeignKey(PeriodoProgramacion, on_delete=models.PROTECT)
    def clean(self):
        if self.assignment.organization_id != self.organization_id or self.period.organization_id != self.organization_id: raise ValidationError("Asignación o periodo incompatible.")


class JornadaBorrador(UuidTenantModel):
    draft = models.ForeignKey(BorradorProgramacion, on_delete=models.PROTECT, related_name="assignments")
    assignment = models.ForeignKey(Asignacion, on_delete=models.PROTECT)
    employee = models.ForeignKey(Empleado, on_delete=models.PROTECT)
    branch = models.ForeignKey(Sucursal, on_delete=models.PROTECT)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    start_local = models.DateTimeField()
    end_local = models.DateTimeField()
    start_offset = models.IntegerField()
    end_offset = models.IntegerField()
    timezone = models.CharField(max_length=64)
    role = models.ForeignKey(Rol, null=True, blank=True, on_delete=models.PROTECT)
    station = models.ForeignKey(Estacion, null=True, blank=True, on_delete=models.PROTECT)
    shift = models.ForeignKey(Turno, null=True, blank=True, on_delete=models.PROTECT)
    labels = models.JSONField(default=dict)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["draft", "assignment"], name="schedule_draft_assignment_uniq"), models.CheckConstraint(condition=models.Q(ends_at__gt=models.F("starts_at")), name="schedule_draft_positive_interval")]
        indexes = [models.Index(fields=["organization", "employee", "starts_at", "ends_at"])]
    def clean(self):
        if not self.role_id and not self.station_id: raise ValidationError("Se requiere rol o estación.")
        if self.ends_at <= self.starts_at: raise ValidationError({"ends_at": "Debe ser posterior al inicio."})
        if self.draft.organization_id != self.organization_id or self.employee.organization_id != self.organization_id or self.branch.organization_id != self.organization_id: raise ValidationError("Referencia fuera de organización.")
        if self.start_local.date() < self.draft.period.date_from or self.start_local.date() > self.draft.period.date_to: raise ValidationError({"start_local": "Fuera del periodo."})


class DescansoBorrador(UuidTenantModel):
    draft = models.ForeignKey(BorradorProgramacion, on_delete=models.PROTECT, related_name="breaks")
    assignment = models.ForeignKey(Asignacion, on_delete=models.PROTECT)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    start_local = models.DateTimeField()
    end_local = models.DateTimeField()
    start_offset = models.IntegerField()
    end_offset = models.IntegerField()
    class Meta: constraints = [models.CheckConstraint(condition=models.Q(ends_at__gt=models.F("starts_at")), name="schedule_break_positive_interval")]
    def clean(self):
        if self.ends_at <= self.starts_at: raise ValidationError({"ends_at": "El descanso debe ser positivo."})
