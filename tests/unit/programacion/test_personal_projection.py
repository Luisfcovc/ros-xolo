def test_personal_projection_module_is_available():
    from ros_xolo.programacion.selectors.personal import get_personal_schedule
    assert callable(get_personal_schedule)
