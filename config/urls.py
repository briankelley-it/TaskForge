from django.contrib import admin
from django.urls import include, path

from projects.views import home

urlpatterns = [
    path("", home, name="home"),
    path("projects/", include("projects.urls")),
    path("projects/<int:project_pk>/", include("tasks.urls")),
    path("projects/<int:project_pk>/activity/", include("activity.urls")),
    path("accounts/", include("allauth.urls")),
    path("admin/", admin.site.urls),
]
