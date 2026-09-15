"""Measure repeatable server-side schedule queries and complete export lifecycles."""

from __future__ import annotations

import json
import platform
import time
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ros_xolo.core.models import Organizacion
from ros_xolo.core.services.authorization import ActorContext
from ros_xolo.programacion.models import PeriodoProgramacion
from ros_xolo.programacion.selectors.personal import get_personal_schedule
from ros_xolo.programacion.selectors.planning import get_published
from ros_xolo.programacion.services.exports import request_export


def _stats(values):
    ordered = sorted(values)
    return {"samples_ms": values, "p95_ms": ordered[max(0, int(len(ordered) * .95) - 1)], "under_3s_rate": sum(value <= 3000 for value in values) / len(values)}


class Command(BaseCommand):
    help = "Mide 100 consultas colectivas/personales y cinco exportaciones de cada formato."

    def add_arguments(self, parser):
        parser.add_argument("--scenario", default="reference-week")
        parser.add_argument("--samples", type=int, default=100)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        if options["scenario"] != "reference-week" or options["samples"] < 1:
            raise CommandError("Usa reference-week y un número positivo de muestras.")
        from django.contrib.auth import get_user_model
        User = get_user_model()
        org = Organizacion.objects.filter(name="DEMO: XOLO").first()
        planner = User.objects.filter(username="demo.planner.all").first()
        personal = User.objects.filter(username="demo.employee.a").first()
        period = PeriodoProgramacion.objects.filter(organization=org, current_publication_id__isnull=False).first() if org else None
        if not all((org, planner, personal, period)):
            raise CommandError("Ejecuta seed_demo antes del benchmark.")
        planner_actor, personal_actor = ActorContext(planner.id, org.id), ActorContext(personal.id, org.id)
        collective, personal_times = [], []
        for _ in range(options["samples"]):
            started = time.perf_counter(); get_published(planner_actor, period.id); collective.append(round((time.perf_counter()-started)*1000, 3))
            started = time.perf_counter(); get_personal_schedule(personal_actor, period.date_from, period.date_to); personal_times.append(round((time.perf_counter()-started)*1000, 3))
        exports = {}
        for export_format in ("png", "pdf"):
            times = []
            for _ in range(5):
                started = time.perf_counter(); request_export(planner_actor, period.id, export_format); times.append(round((time.perf_counter()-started)*1000, 3))
            exports[export_format] = {"samples_ms": times, "max_under_30s": max(times) <= 30000}
        result = {"scenario": "reference-week", "environment": {"python": platform.python_version(), "platform": platform.platform()}, "collective": _stats(collective), "personal": _stats(personal_times), "exports": exports, "criteria_pass": min(_stats(collective)["under_3s_rate"], _stats(personal_times)["under_3s_rate"]) >= .95 and all(item["max_under_30s"] for item in exports.values())}
        path = Path(options["output"]).resolve(); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        if not result["criteria_pass"]:
            raise CommandError("El benchmark no cumplió los criterios de rendimiento.")
        self.stdout.write(self.style.SUCCESS(f"Benchmark registrado en {path}"))
