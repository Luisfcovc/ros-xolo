"""T073 Q4: planner edits breaks; the employee projection receives snapshots only."""

import json
from pathlib import Path

from django.template.loader import render_to_string
from playwright.sync_api import sync_playwright


def test_q4_break_add_change_remove_and_field_error_visibility():
    html = render_to_string("programacion/planning.html", {"period_id": "period-a"})
    form_script = Path("ros_xolo/programacion/static/programacion/assignment_form.js").read_text(encoding="utf-8")
    planning_script = Path("ros_xolo/programacion/static/programacion/planning.js").read_text(encoding="utf-8")
    initial = {"assignments": [{"assignment_id": "aaaaaaaa-0000-4000-8000-000000000001", "employee_id": "aaaaaaaa-0000-4000-8000-000000000002", "starts_at": "2026-09-21T09:00:00Z", "ends_at": "2026-09-21T17:00:00Z", "role_id": "aaaaaaaa-0000-4000-8000-000000000003", "station_id": None, "breaks": []}], "base_publication": {"version": 1}, "has_pending_changes": True, "alerts": []}
    invalid = {"error": {"code": "invalid_break", "message": "Pausa inválida.", "fields": [{"path": "assignments[0].breaks[0].ends_at", "code": "invalid_break"}]}}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
        page = browser.new_page()
        def api(route, request):
            route.fulfill(status=200 if request.method == "GET" else 422, headers={"Content-Type": "application/json", "ETag": '"base"'}, body=json.dumps(initial if request.method == "GET" else invalid))
        page.route("**/api/v1/planning/periods/period-a/draft", api)
        page.set_content(f'<base href="http://xolo.test/">{html}')
        page.add_script_tag(content=form_script)
        page.add_script_tag(content=planning_script)
        page.get_by_text("Contenido guardado cargado.").wait_for()
        page.get_by_role("button", name="Agregar pausa").click()
        pause = page.locator(".break")
        pause.locator('[data-break-field="starts_at"]').fill("2026-09-21T12:00")
        pause.locator('[data-break-field="ends_at"]').fill("2026-09-21T12:30")
        page.get_by_role("button", name="Guardar cambios").click()
        pause.locator('[data-break-errors="ends_at"]').get_by_text("Pausa inválida.").wait_for()
        pause.get_by_role("button", name="Retirar pausa").click()
        assert page.locator(".break").count() == 0
        browser.close()
