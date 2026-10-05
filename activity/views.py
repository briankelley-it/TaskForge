from django.views.generic import ListView

from projects.permissions import ProjectMemberMixin


class ActivityFeedView(ProjectMemberMixin, ListView):
    template_name = "activity/activity_list.html"
    context_object_name = "activities"
    paginate_by = 30

    def get_queryset(self):
        return self.project.activities.select_related("actor", "target_task")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "activity"
        return context
