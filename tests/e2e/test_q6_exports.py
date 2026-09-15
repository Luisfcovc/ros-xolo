"""T081/T089 acceptance contract for Q6 export controls and private download."""

from pathlib import Path


def test_q6_planner_can_select_png_or_pdf_and_sees_the_pending_revision_warning():
    controls = Path(
        "ros_xolo/programacion/templates/programacion/export_controls.html"
    ).read_text(encoding="utf-8")

    assert 'value="png"' in controls
    assert 'value="pdf"' in controls
    assert "Se exportará la versión publicada" in controls
    assert "X-CSRFToken" in controls
    assert "/api/v1/planning/periods/" in controls


def test_q6_file_route_reauthorizes_instead_of_exposing_a_public_media_url():
    view = Path("ros_xolo/programacion/views/export_api.py").read_text(encoding="utf-8")
    urls = Path("ros_xolo/programacion/urls.py").read_text(encoding="utf-8")

    assert "get_export_file(actor, export_id)" in view
    assert "as_attachment=True" in view
    assert "planning/exports/<uuid:export_id>/file" in urls
    assert "MEDIA_URL" not in view
