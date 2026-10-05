from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("new/", views.ProjectCreateView.as_view(), name="create"),
    path("<int:pk>/star/", views.toggle_star, name="toggle_star"),
    path("<int:pk>/members/", views.ProjectMembersView.as_view(), name="members"),
    path("<int:pk>/edit/", views.ProjectUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.ProjectDeleteView.as_view(), name="delete"),
    path("<int:pk>/members/invite/", views.invite_member, name="invite_member"),
    path("<int:pk>/members/<int:user_id>/remove/", views.remove_member, name="remove_member"),
]
