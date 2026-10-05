from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notifications_panel, name="panel"),
    path("badge/", views.notifications_badge, name="badge"),
]
