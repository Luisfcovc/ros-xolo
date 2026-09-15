from django.urls import path
from .views import browser, export_api, history_api, personal_api, planning_api

urlpatterns = [
    path("api/v1/planning/branches", planning_api.branches),
    path("api/v1/planning/branches/<uuid:branch_id>/catalogs", planning_api.catalogs),
    path("api/v1/planning/periods", planning_api.periods),
    path("api/v1/planning/periods/<uuid:period_id>/draft", planning_api.draft),
    path("api/v1/planning/periods/<uuid:period_id>/resolve-shift", planning_api.resolve_shift_view),
    path("api/v1/planning/periods/<uuid:period_id>/publish", planning_api.publish),
    path("api/v1/planning/periods/<uuid:period_id>/published", planning_api.published),
    path("api/v1/planning/periods/<uuid:period_id>/exports", export_api.create_export),
    path("api/v1/planning/exports/<uuid:export_id>", export_api.export_status),
    path("api/v1/planning/exports/<uuid:export_id>/file", export_api.export_file),
    path("api/v1/planning/periods/<uuid:period_id>/versions", history_api.versions),
    path("api/v1/planning/periods/<uuid:period_id>/versions/<int:version>", history_api.version_detail),
    path("api/v1/planning/alerts", history_api.alerts),
    path("api/v1/me/schedule", personal_api.personal_schedule),
    path("api/v1/me/history", history_api.personal_history),
    path("api/v1/me/periods/<uuid:period_id>/versions/<int:version>", history_api.personal_version),
    path("planning/", browser.planning, name="planning"),
    path("planning/periods/<uuid:period_id>/", browser.planning, name="planning-period"),
    path("me/schedule/", browser.personal_schedule, name="personal-schedule"),
    path("planning/periods/<uuid:period_id>/history/", browser.history, name="planning-history"),
]
