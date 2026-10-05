from django.urls import path

from . import views

app_name = "activity"

# Included under projects/<int:project_pk>/activity/
urlpatterns = [
    path("", views.ActivityFeedView.as_view(), name="feed"),
]
