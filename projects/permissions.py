"""Project access rules, shared by every view that works inside a project.

Rules:
- Not a member: 404. Answering 403 would confirm the project exists.
- A member but not the owner, on an owner-only action: 403. They already know
  the project exists, so a clear "not allowed" is more helpful than a 404.

Class-based views use ProjectMemberMixin / ProjectOwnerMixin. Function-based
HTMX endpoints call get_membership() directly.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404

from .models import Membership


def get_membership(user, project_id: int, *, owner_only: bool = False) -> Membership:
    """Return the user's membership of the project, or raise Http404 / PermissionDenied."""
    if not user.is_authenticated:
        raise Http404
    try:
        membership = Membership.objects.select_related("project", "project__owner").get(
            project_id=project_id, user=user
        )
    except Membership.DoesNotExist:
        raise Http404("Project not found.") from None
    if owner_only and not membership.is_owner:
        raise PermissionDenied("Only the project owner can do that.")
    return membership


class ProjectMemberMixin(LoginRequiredMixin):
    """Loads self.project and self.membership from the URL, or responds 404.

    Expects the project's id in the URL as `project_pk`, or as `pk` for views
    whose object is the project itself.
    """

    owner_only = False
    project_url_kwarg = "project_pk"

    def dispatch(self, request, *args, **kwargs):
        # LoginRequiredMixin sends anonymous users to the login page before we get here.
        if request.user.is_authenticated:
            project_id = kwargs.get(self.project_url_kwarg, kwargs.get("pk"))
            self.membership = get_membership(request.user, project_id, owner_only=self.owner_only)
            self.project = self.membership.project
            # Templates show the star state on the project, as on the dashboard.
            self.project.is_starred = self.membership.is_starred
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.project
        context["membership"] = self.membership
        return context


class ProjectOwnerMixin(ProjectMemberMixin):
    owner_only = True
