from django.urls import path
from . import views

app_name = "dashboard"
urlpatterns = [
    path("", views.home, name="home"),
    path("users/", views.users, name="users"),
    path("tools/<slug:tool_slug>/", views.tool, name="tool"),
    path("api/lastmile/interfaces/", views.lastmile_interfaces, name="lastmile_interfaces"),
    path("api/ios/upload/start/", views.ios_upload_start, name="ios_upload_start"),
    path("api/ios/upload/status/<str:job_id>/", views.ios_upload_status, name="ios_upload_status"),
    path("api/live/start/", views.live_tool_start, name="live_tool_start"),
    path("api/live/status/<str:job_id>/", views.live_tool_status, name="live_tool_status"),
    path("api/mac/update/", views.mac_update, name="mac_update"),
    path("api/mac/update-all/", views.mac_update_all, name="mac_update_all"),
    path("users/add/", views.add_user, name="add_user"),
    path("health/", views.health, name="health"),
]
