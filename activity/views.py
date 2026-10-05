from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.generic import ListView

from projects.permissions import ProjectMemberMixin

from . import services


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


# --- Notifications bell -----------------------------------------------------------


@login_required
def notifications_badge(request: HttpRequest) -> HttpResponse:
    """The unread count on the bell. Loaded by HTMX after the page, so it never slows
    down or adds queries to the page itself, and refreshed every minute."""
    return render(
        request,
        "activity/partials/notification_badge.html",
        {"unread": services.unread_count(request.user)},
    )


@login_required
def notifications_panel(request: HttpRequest) -> HttpResponse:
    """The dropdown list. Opening it marks everything as read and clears the badge."""
    items = list(services.notifications_for(request.user)[:12])
    seen_before = request.user.notifications_seen_at
    services.mark_notifications_seen(request.user)
    return render(
        request,
        "activity/partials/notification_panel.html",
        {"items": items, "seen_before": seen_before, "unread": 0},
    )
