"""Create a deterministic, isolated demo dataset without exposing credentials."""

from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ros_xolo.core.models import (
    Area, Empleado, Estacion, HabilitacionSucursal, Organizacion, PermisoPlaneacion,
    Rol, Sucursal, Turno, UsuarioOrganizacion,
)
from ros_xolo.core.services.authorization import ActorContext
from ros_xolo.programacion.models import PeriodoProgramacion
from ros_xolo.programacion.selectors.planning import get_draft
from ros_xolo.programacion.services.drafts import replace_draft
from ros_xolo.programacion.services.periods import PeriodOverlap, create_period
from ros_xolo.programacion.services.publication import publish_period


NAMESPACE = uuid.UUID("c12a6f4d-4436-4cb5-a8bb-d1d9497f997d")


def _id(name: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, name)


class Command(BaseCommand):
    help = "Crea datos demo deterministas para validación; nunca muestra contraseñas."

    def add_arguments(self, parser):
        parser.add_argument("--week-start", type=date.fromisoformat, required=True)

    def _user(self, username, password):
        User = get_user_model()
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user

    def handle(self, *args, **options):
        password = os.getenv("ROS_XOLO_DEMO_PASSWORD")
        if not password:
            raise CommandError("Define ROS_XOLO_DEMO_PASSWORD para crear cuentas demo.")
        week_start = options["week_start"]
        if week_start.weekday() != 0:
            raise CommandError("--week-start debe ser lunes (ISO-8601).")

        with transaction.atomic():
            org, _ = Organizacion.objects.get_or_create(
                id=_id("demo-org"), defaults={"name": "DEMO: XOLO"}
            )
            if org.name != "DEMO: XOLO":
                raise CommandError("La organización demo existente no está marcada como DEMO.")
            other_org, _ = Organizacion.objects.get_or_create(
                id=_id("demo-isolation-org"), defaults={"name": "DEMO: aislamiento"}
            )
            if other_org.name != "DEMO: aislamiento":
                raise CommandError("La organización de aislamiento no está marcada como DEMO.")
            jaltepec, _ = Sucursal.objects.get_or_create(
                id=_id("branch-jaltepec"), organization=org,
                defaults={"name": "XOLO Jaltepec", "timezone": "America/Mexico_City"},
            )
            second, _ = Sucursal.objects.get_or_create(
                id=_id("branch-second"), organization=org,
                defaults={"name": "Sucursal de prueba Oriente", "timezone": "America/New_York"},
            )
            Sucursal.objects.get_or_create(
                id=_id("branch-isolation"), organization=other_org,
                defaults={"name": "Sucursal aislada", "timezone": "America/Mexico_City"},
            )
            role, _ = Rol.objects.get_or_create(
                id=_id("role-operacion"), organization=org, defaults={"name": "Operación"}
            )
            role.applicable_branches.add(jaltepec, second)
            area, _ = Area.objects.get_or_create(
                id=_id("area-jaltepec"), organization=org, branch=jaltepec,
                defaults={"name": "Operación"},
            )
            Estacion.objects.get_or_create(
                id=_id("station-jaltepec"), organization=org, branch=jaltepec, area=area,
                defaults={"name": "Estación 1"},
            )
            Turno.objects.get_or_create(
                id=_id("shift-day"), organization=org,
                defaults={"name": "Diurno", "start_local_time": "09:00", "end_local_time": "17:00", "end_day_offset": 0},
            )[0].applicable_branches.add(jaltepec, second)

            employees = []
            for number in range(1, 21):
                employee, _ = Empleado.objects.get_or_create(
                    id=_id(f"employee-{number}"), organization=org,
                    defaults={"display_name": f"Personal demo {number:02d}"},
                )
                employees.append(employee)
                for branch in (jaltepec, second):
                    HabilitacionSucursal.objects.get_or_create(
                        id=_id(f"enable-{number}-{branch.id}"), organization=org,
                        employee=employee, branch=branch, defaults={"enabled": True},
                    )

            users = {name: self._user(f"demo.{name}", password) for name in (
                "planner.jaltepec", "planner.all", "employee.a", "employee.b", "planner.employee"
            )}
            employee_accounts = {"employee.a": employees[0], "employee.b": employees[1], "planner.employee": employees[2]}
            for username, user in users.items():
                UsuarioOrganizacion.objects.get_or_create(
                    id=_id(f"membership-{username}"), organization=org, user=user,
                    defaults={"employee": employee_accounts.get(username), "active": True},
                )
            for username, branches in (("planner.jaltepec", (jaltepec,)), ("planner.all", (jaltepec, second)), ("planner.employee", (jaltepec,))):
                for branch in branches:
                    PermisoPlaneacion.objects.get_or_create(
                        id=_id(f"grant-{username}-{branch.id}"), organization=org, user=users[username],
                        branch=branch, defaults={"enabled": True},
                    )

            actor = ActorContext(user_id=users["planner.all"].id, organization_id=org.id)
            period = PeriodoProgramacion.objects.filter(
                organization=org, branch=jaltepec, date_from=week_start, date_to=week_start + timedelta(days=6)
            ).first()
            if period is None:
                try:
                    period, _, _ = create_period(actor, jaltepec.id, week_start, week_start + timedelta(days=6))
                except PeriodOverlap as exc:
                    raise CommandError("La semana de referencia se traslapa con datos demo existentes.") from exc
                rows = []
                for index, employee in enumerate(employees):
                    start_day = week_start + timedelta(days=index % 5)
                    rows.append({
                        "assignment_id": str(_id(f"reference-assignment-{week_start}-{index}")),
                        "employee_id": str(employee.id),
                        "starts_at": f"{start_day.isoformat()}T09:00:00-06:00",
                        "ends_at": f"{start_day.isoformat()}T17:00:00-06:00",
                        "role_id": str(role.id), "station_id": None, "shift_id": None, "breaks": [],
                    })
                draft = get_draft(actor, period.id)
                replace_draft(actor, period.id, draft["etag"], {"assignments": rows})
                draft = get_draft(actor, period.id)
                publish_period(actor, period.id, draft["etag"])

        self.stdout.write(self.style.SUCCESS(
            f"Demo listo: organización={org.id}; reference-week={period.id}; usuarios=demo.planner.jaltepec,demo.planner.all,demo.employee.a,demo.employee.b,demo.planner.employee"
        ))
