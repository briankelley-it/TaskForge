"""Project pages (class-based views) and member HTMX endpoints (function-based views).

Convention used across TaskForge: full pages are CBVs; small HTMX endpoints that
return a partial are FBVs, because their flow is easier to read top to bottom.
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, TemplateView, UpdateView

from tasks.models import Task

from . import services
from .dashboard import VIEWS, build_dashboard
from .forms import CoverForm, InviteForm, ProjectForm
from .htmx import is_htmx
from .models import Membership, Project
from .permissions import ProjectMemberMixin, ProjectOwnerMixin, get_membership

User = get_user_model()


def home(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("projects:dashboard")
    return render(request, "home.html")


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "projects/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dashboard = build_dashboard(self.request.user, self.request.GET.get("view", "all"))
        context.update(dashboard=dashboard, projects=dashboard.projects, views=VIEWS)
        return context


@login_required
@require_POST
def toggle_star(request: HttpRequest, pk: int) -> HttpResponse:
    """Star or unstar a project. HTMX swaps just the star button."""
    membership = get_membership(request.user, pk)
    starred = services.toggle_star(membership)
    if is_htmx(request):
        project = membership.project
        project.is_starred = starred
        return render(request, "projects/partials/star_button.html", {"project": project})
    return redirect("projects:dashboard")


@login_required
def search(request: HttpRequest) -> HttpResponse:
    """Search projects and task titles across every project the user belongs to.

    The top bar asks for the dropdown partial on every keystroke (via HTMX); pressing
    Enter submits the same form to the full results page.
    """
    query = request.GET.get("q", "").strip()
    limit = 5 if is_htmx(request) else 50
    projects, tasks = [], []
    if query:
        mine = Project.objects.for_user(request.user)
        projects = list(
            mine.filter(Q(name__icontains=query) | Q(description__icontains=query))[:limit]
        )
        tasks = list(
            Task.objects.filter(project__in=mine, title__icontains=query)
            .select_related("project")
            .order_by("-updated_at")[: limit * 2]
        )
    template = (
        "projects/partials/search_results.html" if is_htmx(request) else "projects/search.html"
    )
    return render(
        request, template, {"query": query, "results_projects": projects, "results_tasks": tasks}
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
        # The bound form has already put any new cover on the instance, so read the old
        # filename from the database, and delete that file once the new one is saved.
        old_cover = Project.objects.values_list("cover", flat=True).get(pk=self.project.pk)
        response = super().form_valid(form)
        if old_cover and old_cover != self.object.cover.name:
            self.object.cover.storage.delete(old_cover)
        messages.success(self.request, "Project updated.")
        return response


@login_required
def project_cover(request: HttpRequest, pk: int) -> HttpResponse:
    """The "Change cover" modal: pick a file with the system file picker (or drop one),
    preview it, upload. Owners only, like the rest of the project's settings."""
    project = get_membership(request.user, pk, owner_only=True).project
    if request.method == "POST":
        if request.POST.get("remove"):
            services.remove_cover(project)
            return cover_saved(request, "Cover removed.")
        form = CoverForm(request.POST, request.FILES, instance=project)
        if form.is_valid():
            services.set_cover(project, form.cleaned_data["cover"])
            return cover_saved(request, "Cover updated.")
    else:
        form = CoverForm(instance=project)
    template = (
        "projects/partials/cover_form.html" if is_htmx(request) else "projects/cover_page.html"
    )
    next_url = request.POST.get("next") or request.GET.get("next", "")
    return render(request, template, {"project": project, "form": form, "next_url": next_url})


def cover_saved(request: HttpRequest, message: str) -> HttpResponse:
    messages.success(request, message)
    if is_htmx(request):
        # Covers appear in several places (cards, header), so reload the page.
        response = HttpResponse(status=204)
        response["HX-Refresh"] = "true"
        return response
    # Only follow "next" if it points back at this site (no open redirects).
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
        return redirect(next_url)
    return redirect("projects:dashboard")


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
