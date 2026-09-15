from pathlib import Path

def test_schedule_hides_data_when_offline():
    script = Path('ros_xolo/programacion/static/programacion/personal_schedule.js').read_text(encoding='utf-8')
    assert "window.addEventListener('offline'" in script
    assert "AbortController" in script
    assert "setInterval" in script
