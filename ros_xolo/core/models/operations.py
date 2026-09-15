import uuid
from django.conf import settings
from django.db import models
from .catalogs import Empleado, Organizacion, Sucursal, UUIDModel


class Asignacion(UUIDModel):
    organization = models.ForeignKey(Organizacion, on_delete=models.PROTECT)
    kind = models.CharField(max_length=32, default="jornada")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class RecordedOperation(UUIDModel):
    organization = models.ForeignKey(Organizacion, on_delete=models.PROTECT)
    branch = models.ForeignKey(Sucursal, null=True, blank=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    occurred_at = models.DateTimeField(auto_now_add=True)
    correlation_id = models.UUIDField(default=uuid.uuid4)
    class Meta: abstract = True


class Evento(RecordedOperation):
    type = models.CharField(max_length=100)
    subject_id = models.UUIDField()
    payload = models.JSONField(default=dict)


class Auditoria(RecordedOperation):
    operation = models.CharField(max_length=100)
    subject_id = models.UUIDField()
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    outcome = models.CharField(max_length=32, default="success")


class Incidencia(RecordedOperation):
    employee = models.ForeignKey(Empleado, null=True, blank=True, on_delete=models.PROTECT)
    period_id = models.UUIDField()
    type = models.CharField(max_length=100)
    affected_assignment_ids = models.JSONField(default=list)
    status = models.CharField(max_length=32, default="open")
    resolved_at = models.DateTimeField(null=True, blank=True)
    source_event = models.ForeignKey(Evento, null=True, on_delete=models.PROTECT, related_name="source_incidents")
    resolution_event = models.ForeignKey(Evento, null=True, blank=True, on_delete=models.PROTECT, related_name="resolved_incidents")
