def test_schedule_requires_authentication(client):
    response = client.get('/api/v1/me/schedule?from=2026-09-14&to=2026-09-14')
    assert response.status_code == 401
    assert response.json()['error']['code'] == 'unauthenticated'

def test_schedule_does_not_accept_an_employee_selector(client, django_user_model):
    user = django_user_model.objects.create_user('employee')
    client.force_login(user)
    client.session['organization_id'] = '00000000-0000-0000-0000-000000000000'
    response = client.get('/api/v1/me/schedule?from=2026-09-14&to=2026-09-14&employee_id=other')
    assert response.status_code == 422
