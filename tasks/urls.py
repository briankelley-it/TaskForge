from django.urls import path

from . import views

app_name = "tasks"

# Included under projects/<int:project_pk>/
urlpatterns = [
    path("", views.BoardView.as_view(), name="board"),
    path("tasks/new/", views.task_create, name="create"),
    path("tasks/<int:pk>/edit/", views.task_update, name="update"),
    path("tasks/<int:pk>/delete/", views.task_delete, name="delete"),
    path("tasks/<int:pk>/move/", views.task_move, name="move"),
]
