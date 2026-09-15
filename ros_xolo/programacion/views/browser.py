"""Authenticated HTML pages for the schedule workflow."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def planning(request, period_id=None):
    return render(request, "programacion/planning.html", {"period_id": period_id})


@login_required
def personal_schedule(request):
    return render(request, "programacion/personal_schedule.html")


@login_required
def history(request, period_id):
    return render(request, "programacion/history.html", {"period_id": period_id})
