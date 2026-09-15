import json
from pathlib import Path

from django.template.loader import render_to_string
from playwright.sync_api import sync_playwright


def test_q3_conflict_correction_keeps_pending_publication_visible():
    html = render_to_string("programacion/planning.html", {"period_id": "period-a"})
    script = Path("ros_xolo/programacion/static/programacion/planning.js").read_text(
        encoding="utf-8"
    )
    initial = {
        "assignments": [{
            "assignment_id": "aaaaaaaa-0000-4000-8000-000000000001",
            "employee_id": "aaaaaaaa-0000-4000-8000-000000000002",
            "starts_at": "2026-09-21T15:00:00Z",
            "ends_at": "2026-09-21T23:00:00Z",
            "role_id": "aaaaaaaa-0000-4000-8000-000000000003",
            "station_id": None,
        }],
        "base_publication": {"version": 1},
        "has_pending_changes": True,
        "alerts": [{
            "type": "revision_pending",
            "priority": "medium",
            "required_action": "Revisar las diferencias y publicar.",
        }],
    }
    conflict = {
        "error": {
            "code": "overlap",
            "message": "La jornada coincide con otra asignación.",
            "action": "Corrige el horario o coordina con un planeador autorizado.",
            "fields": [{"path": "assignments[0].starts_at", "code": "overlap"}],
            "conflicts": [{"restricted": True, "scope": "draft"}],
        }
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="/usr/bin/chromium", args=["--no-sandbox"]
        )
        page = browser.new_page()

        def api(route, request):
            if request.method == "GET":
                route.fulfill(
                    status=200,
                    headers={"Content-Type": "application/json", "ETag": '"base"'},
                    body=json.dumps(initial),
                )
            else:
                route.fulfill(
                    status=409,
                    headers={"Content-Type": "application/json"},
                    body=json.dumps(conflict),
                )

        page.route("**/api/v1/planning/periods/period-a/draft", api)
        page.set_content(f'<base href="http://xolo.test/">{html}')
        page.add_script_tag(content=script)
        page.get_by_text("Contenido guardado cargado.").wait_for()
        page.get_by_role("button", name="Guardar cambios").click()
        page.get_by_text("Este intervalo se traslapa", exact=False).wait_for()
        assert "publicación pendiente se conserva" in page.locator("#save-state").inner_text()
        assert "Centro" not in page.content()
        assert "11:00" not in page.content()
        browser.close()
