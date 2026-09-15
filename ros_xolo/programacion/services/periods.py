from django.db import IntegrityError, transaction
from ros_xolo.core.models import Auditoria, Evento, Sucursal
from ros_xolo.core.services.authorization import authorize_planner
from ros_xolo.core.services.locking import organization_lock
from ros_xolo.programacion.models import BorradorProgramacion, PeriodoProgramacion


class PeriodOverlap(ValueError): pass


def create_period(actor, branch_id, date_from, date_to):
    authorize_planner(actor, branch_id)
    if date_to < date_from: raise ValueError("date_to no puede ser anterior a date_from.")
    with organization_lock(actor.organization_id) as organization:
        branch = Sucursal.objects.get(pk=branch_id, organization=organization, active=True)
        authorize_planner(actor, branch.id)
        if PeriodoProgramacion.objects.filter(organization=organization, branch=branch, date_from__lte=date_to, date_to__gte=date_from).exists():
            raise PeriodOverlap("period_overlap")
        with transaction.atomic():
            period = PeriodoProgramacion.objects.create(organization=organization, branch=branch, date_from=date_from, date_to=date_to, timezone=branch.timezone, created_by_id=actor.user_id)
            draft = BorradorProgramacion.objects.create(organization=organization, period=period, updated_by_id=actor.user_id)
            event = Evento.objects.create(organization=organization, branch=branch, actor_id=actor.user_id, type="scheduling.period_created", subject_id=period.id, payload={"period_id": str(period.id)})
            Auditoria.objects.create(organization=organization, branch=branch, actor_id=actor.user_id, operation="scheduling.period.create", subject_id=period.id, after={"date_from": date_from.isoformat(), "date_to": date_to.isoformat()})
            return period, draft, event
