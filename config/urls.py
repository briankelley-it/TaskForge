from django.apps import apps
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts.views import demo_login
from projects.views import home, search
from tasks.views import my_tasks

urlpatterns = [
    path("", home, name="home"),
    path("search/", search, name="search"),
    path("my-tasks/", my_tasks, name="my_tasks"),
    path("notifications/", include("activity.notification_urls")),
    path("projects/", include("projects.urls")),
    path("projects/<int:project_pk>/", include("tasks.urls")),
    path("projects/<int:project_pk>/activity/", include("activity.urls")),
    path("accounts/demo/", demo_login, name="demo_login"),
    path("accounts/", include("allauth.urls")),
    path("admin/", admin.site.urls),
]

# Serve uploaded files from Django in development only; production uses a real file server.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Live browser reload, only when config.settings.dev has installed it.
if apps.is_installed("django_browser_reload"):
    urlpatterns.append(path("__reload__/", include("django_browser_reload.urls")))
