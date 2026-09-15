from django.conf import settings


def test_internal_health_probe_is_exempt_from_https_redirect():
    assert r"^health$" in settings.SECURE_REDIRECT_EXEMPT
