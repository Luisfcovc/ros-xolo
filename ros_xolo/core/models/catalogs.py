from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.core.exceptions import ValidationError
from django.db import models


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=__import__("uuid").uuid4, editable=False)
    class Meta: abstract = True


class Organizacion(UUIDModel):
    name = models.CharField(max_length=200)
    core_revision = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class TenantModel(UUIDModel):
    organization = models.ForeignKey(Organizacion, on_delete=models.PROTECT)
    class Meta: abstract = True


class Sucursal(TenantModel):
    name = models.CharField(max_length=200)
    timezone = models.CharField(max_length=64)
    active = models.BooleanField(default=True)
    def clean(self):
        try: ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError: raise ValidationError({"timezone": "Debe ser una zona IANA válida."})


class Empleado(TenantModel):
    display_name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)


class HabilitacionSucursal(TenantModel):
    employee = models.ForeignKey(Empleado, on_delete=models.PROTECT)
    branch = models.ForeignKey(Sucursal, on_delete=models.PROTECT)
    enabled = models.BooleanField(default=True)
    changed_at = models.DateTimeField(auto_now=True)
    changed_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.PROTECT)
    class Meta: constraints = [models.UniqueConstraint(fields=["employee", "branch"], name="core_employee_branch_enable_uniq")]
    def clean(self):
        if self.employee.organization_id != self.organization_id or self.branch.organization_id != self.organization_id: raise ValidationError("Las referencias deben pertenecer a la organización.")


class ApplicableBranches(TenantModel):
    name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    applicable_branches = models.ManyToManyField(Sucursal, blank=True)
    class Meta: abstract = True


class Rol(ApplicableBranches): pass


class Area(TenantModel):
    branch = models.ForeignKey(Sucursal, on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)


class Estacion(TenantModel):
    branch = models.ForeignKey(Sucursal, on_delete=models.PROTECT)
    area = models.ForeignKey(Area, on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    def clean(self):
        if self.area.branch_id != self.branch_id or self.branch.organization_id != self.organization_id: raise ValidationError("Área, sucursal y organización incompatibles.")


class Turno(ApplicableBranches):
    start_local_time = models.TimeField()
    end_local_time = models.TimeField()
    end_day_offset = models.PositiveSmallIntegerField(default=0)
