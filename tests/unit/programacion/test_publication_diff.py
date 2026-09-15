from ros_xolo.programacion.services.revisions import build_publication_changes


def _assignment(identifier, employee="employee-a", start="2026-09-21T15:00:00+00:00"):
    return {
        "assignment_id": identifier,
        "employee_id": employee,
        "starts_at": start,
        "ends_at": "2026-09-21T23:00:00+00:00",
        "role_id": "role-a",
        "station_id": None,
        "shift_id": None,
        "timezone": "America/Mexico_City",
        "start_offset": -21600,
        "end_offset": -21600,
        "labels": {"employee": "Ana", "role": "Cocina"},
        "breaks": [],
    }


def test_semantic_diff_reports_assignment_and_roster_added_modified_removed():
    before_assignments = [_assignment("kept"), _assignment("removed")]
    after_assignments = [
        _assignment("kept", start="2026-09-21T16:00:00+00:00"),
        _assignment("added"),
    ]
    before_roster = [
        {"employee_id": "employee-a", "employee_label": "Ana"},
        {"employee_id": "employee-old", "employee_label": "Old"},
        {"employee_id": "employee-renamed", "employee_label": "Antes"},
    ]
    after_roster = [
        {"employee_id": "employee-a", "employee_label": "Ana"},
        {"employee_id": "employee-new", "employee_label": "New"},
        {"employee_id": "employee-renamed", "employee_label": "Después"},
    ]
    changes = build_publication_changes(
        before_assignments, after_assignments, before_roster, after_roster
    )
    assert [item["kind"] for item in changes] == [
        "assignment_added",
        "assignment_modified",
        "assignment_removed",
        "roster_added",
        "roster_modified",
        "roster_removed",
    ]
    modified = next(item for item in changes if item["kind"] == "assignment_modified")
    assert modified["before"]["starts_at"] != modified["after"]["starts_at"]
    assert modified["changed_fields"] == ["starts_at"]


def test_semantic_diff_ignores_input_order():
    assignments = [_assignment("b"), _assignment("a")]
    roster = [
        {"employee_id": "b", "employee_label": "B"},
        {"employee_id": "a", "employee_label": "A"},
    ]
    assert build_publication_changes(assignments, list(reversed(assignments)), roster, list(reversed(roster))) == []
