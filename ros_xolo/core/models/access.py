from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .catalogs import Empleado, Organizacion, Sucursal, UUIDModel


class UsuarioOrganizacion(UUIDModel):
    organization = models.ForeignKey(Organizacion, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    employee = models.ForeignKey(Empleado, null=True, blank=True, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)
    class Meta: constraints = [models.UniqueConstraint(fields=["user", "organization"], name="core_user_org_uniq")]
    def clean(self):
        if self.employee_id and self.employee.organization_id != self.organization_id: raise ValidationError("El empleado debe pertenecer a la organización.")


class PermisoPlaneacion(UUIDModel):
    organization = models.ForeignKey(Organizacion, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    branch = models.ForeignKey(Sucursal, on_delete=models.PROTECT)
    enabled = models.BooleanField(default=True)
    class Meta: constraints = [models.UniqueConstraint(fields=["user", "branch"], name="core_planner_grant_uniq")]
    def clean(self):
        if self.branch.organization_id != self.organization_id: raise ValidationError("La sucursal debe pertenecer a la organización.")
