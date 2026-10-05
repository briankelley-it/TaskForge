"""Project pages (class-based views) and member HTMX endpoints (function-based views).

Convention used across TaskForge: full pages are CBVs; small HTMX endpoints that
return a partial are FBVs, because their flow is easier to read top to bottom.
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from tasks.models import Task

from . import services
from .forms import InviteForm, ProjectForm
from .htmx import is_htmx
from .models import Membership, Project
from .permissions import ProjectMemberMixin, ProjectOwnerMixin, get_membership

User = get_user_model()


def home(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("projects:dashboard")
    return render(request, "home.html")


class DashboardView(LoginRequiredMixin, ListView):
    template_name = "projects/dashboard.html"
    context_object_name = "projects"

    def get_queryset(self):
        # Two multi-valued joins (memberships and tasks) multiply rows, so every count
        # is distinct. One query for the whole dashboard, however many projects.
        tasks = Task.Status
        return (
            Project.objects.for_user(self.request.user)
            .select_related("owner")
            .annotate(
                member_count=Count("memberships", distinct=True),
                todo_count=Count("tasks", filter=Q(tasks__status=tasks.TODO), distinct=True),
                in_progress_count=Count(
                    "tasks", filter=Q(tasks__status=tasks.IN_PROGRESS), distinct=True
                ),
                done_count=Count("tasks", filter=Q(tasks__status=tasks.DONE), distinct=True),
            )
        )


class ProjectCreateView(LoginRequiredMixin, CreateView):
    form_class = ProjectForm
    template_name = "projects/project_form.html"

    def form_valid(self, form):
        self.object = services.create_project(owner=self.request.user, **form.cleaned_data)
        messages.success(self.request, f"Created “{self.object.name}”.")
        return redirect(self.object)


class ProjectMembersView(ProjectMemberMixin, DetailView):
    template_name = "projects/project_members.html"

    def get_object(self, queryset=None):
        return self.project

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(members_context(self.project, self.membership))
        return context


class ProjectUpdateView(ProjectOwnerMixin, UpdateView):
    form_class = ProjectForm
    template_name = "projects/project_form.html"

    def get_object(self, queryset=None):
        return self.project

    def form_valid(self, form):
        messages.success(self.request, "Project updated.")
        return super().form_valid(form)


class ProjectDeleteView(ProjectOwnerMixin, DeleteView):
    template_name = "projects/project_confirm_delete.html"
    success_url = reverse_lazy("projects:dashboard")

    def get_object(self, queryset=None):
        return self.project

    def form_valid(self, form):
        messages.success(self.request, f"Deleted “{self.project.name}”.")
        return super().form_valid(form)


# --- Members (HTMX) ---------------------------------------------------------------


def members_context(project: Project, membership: Membership, **extra) -> dict:
    memberships = project.memberships.select_related("user").order_by("-role", "joined_at")
    return {
        "project": project,
        "membership": membership,
        "memberships": memberships,
        "invite_form": extra.pop("invite_form", None) or InviteForm(),
        **extra,
    }


def render_members(request: HttpRequest, project: Project, membership: Membership, **extra):
    """Return the members panel for HTMX, or redirect back to the project for plain POSTs."""
    if is_htmx(request):
        context = members_context(project, membership, **extra)
        return render(request, "projects/partials/members.html", context)
    if notice := extra.get("notice"):
        messages.add_message(request, extra.get("notice_level", messages.INFO), notice)
    return redirect("projects:members", pk=project.pk)


@login_required
@require_POST
def invite_member(request: HttpRequest, pk: int) -> HttpResponse:
    membership = get_membership(request.user, pk, owner_only=True)
    project = membership.project
    form = InviteForm(request.POST)
    if not form.is_valid():
        return render_members(request, project, membership, invite_form=form)

    result, user = services.invite_member(project=project, email=form.cleaned_data["email"])
    email = form.cleaned_data["email"]
    notices = {
        services.InviteResult.ADDED: (messages.SUCCESS, f"Added {user} to the project."),
        services.InviteResult.ALREADY_MEMBER: (messages.INFO, f"{user} is already a member."),
        services.InviteResult.NO_SUCH_USER: (
            messages.WARNING,
            f"No TaskForge account uses {email}. Ask them to sign up, then invite them again.",
        ),
    }
    level, notice = notices[result]
    # Keep the typed email in the box only when it didn't work, so it can be corrected.
    invite_form = InviteForm(initial={"email": email}) if user is None else None
    return render_members(
        request,
        project,
        membership,
        notice=notice,
        notice_level=level,
        invite_form=invite_form,
    )


@login_required
@require_POST
def remove_member(request: HttpRequest, pk: int, user_id: int) -> HttpResponse:
    membership = get_membership(request.user, pk, owner_only=True)
    project = membership.project
    member = get_object_or_404(User, pk=user_id, memberships__project=project)
    try:
        services.remove_member(project=project, user=member)
        notice, level = f"Removed {member} from the project.", messages.SUCCESS
    except services.CannotRemoveOwner as exc:
        notice, level = str(exc), messages.ERROR
    return render_members(request, project, membership, notice=notice, notice_level=level)
