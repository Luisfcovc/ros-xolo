"""T028 acceptance contract for the planning screen delivered in T040–T041."""
from pathlib import Path


def test_q1_planning_and_publish_desktop():
    script = Path("ros_xolo/programacion/static/programacion/planning.js").read_text(
        encoding="utf-8"
    )
    template = Path(
        "ros_xolo/programacion/templates/programacion/planning.html"
    ).read_text(encoding="utf-8")
    assert "If-Match" in script
    assert "save-draft" in template
    assert "publish" in template
