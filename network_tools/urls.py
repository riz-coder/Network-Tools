from django.urls import include, path
from django.contrib.auth import views as auth_views

from dashboard import views as dashboard_views

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html", redirect_authenticated_user=True),
        name="login",
    ),
    path("logout/", dashboard_views.logout_user, name="logout"),
    path("", include("dashboard.urls")),
]
