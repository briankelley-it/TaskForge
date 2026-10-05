"""The Kanban board (class-based) and its HTMX endpoints (function-based).

HTMX flow for the modal form:
  1. "New task" or a card does hx-get on the form URL; the form partial is put into #modal.
  2. The form does hx-post. Invalid: the form partial comes back with errors.
     Valid: an empty 204 with an HX-Trigger header. "boardChanged" makes the board
     reload itself, and "closeModal" tells app.js to close the modal.
Without HTMX, the same URLs render full pages and redirect, so nothing depends on JS.
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from projects.htmx import is_htmx
from projects.models import Project
from projects.permissions import ProjectMemberMixin, get_membership

from . import services
from .forms import TaskForm
from .models import Task


def board_columns(project: Project) -> list[dict]:
    """The board's three columns with their tasks: one query for every task."""
    tasks = project.tasks.select_related("assignee").order_by("position", "id")
    columns = {status: [] for status in Task.Status.values}
    for task in tasks:
        columns[task.status].append(task)
    return [
        {"status": status, "label": label, "tasks": columns[status]}
        for status, label in Task.Status.choices
    ]


class BoardView(ProjectMemberMixin, TemplateView):
    def get_template_names(self):
        # The board reloads itself after changes; HTMX only needs the board, not the page.
        if is_htmx(self.request):
            return ["tasks/partials/board.html"]
        return ["tasks/board.html"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["columns"] = board_columns(self.project)
        context["active_tab"] = "board"
        return context


def get_task(user, project_pk: int, pk: int) -> Task:
    """A task in a project the user belongs to. 404 for non-members and for tasks
    that exist but belong to a different project."""
    project = get_membership(user, project_pk).project
    return get_object_or_404(Task.objects.select_related("project"), pk=pk, project=project)


def board_changed(request: HttpRequest, project: Project, message: str) -> HttpResponse:
    if is_htmx(request):
        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps({"boardChanged": None, "closeModal": None})
        return response
    messages.success(request, message)
    return redirect(project)


def render_task_form(request: HttpRequest, project: Project, form: TaskForm, task=None):
    template = "tasks/partials/task_form.html" if is_htmx(request) else "tasks/task_form.html"
    return render(request, template, {"project": project, "form": form, "task": task})


@login_required
def task_create(request: HttpRequest, project_pk: int) -> HttpResponse:
    project = get_membership(request.user, project_pk).project
    if request.method == "POST":
        form = TaskForm(request.POST, project=project)
        if form.is_valid():
            task = services.create_task(
                project=project, created_by=request.user, **form.cleaned_data
            )
            return board_changed(request, project, f"Created “{task.title}”.")
    else:
        status = request.GET.get("status")
        initial = {"status": status if status in Task.Status.values else Task.Status.TODO}
        form = TaskForm(project=project, initial=initial)
    return render_task_form(request, project, form)


@login_required
def task_update(request: HttpRequest, project_pk: int, pk: int) -> HttpResponse:
    task = get_task(request.user, project_pk, pk)
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task, project=task.project)
        if form.is_valid():
            services.update_task(task, **form.cleaned_data)
            return board_changed(request, task.project, "Task updated.")
    else:
        form = TaskForm(instance=task, project=task.project)
    return render_task_form(request, task.project, form, task)


@login_required
@require_POST
def task_delete(request: HttpRequest, project_pk: int, pk: int) -> HttpResponse:
    task = get_task(request.user, project_pk, pk)
    services.delete_task(task)
    return board_changed(request, task.project, f"Deleted “{task.title}”.")


@login_required
@require_POST
def task_move(request: HttpRequest, project_pk: int, pk: int) -> HttpResponse:
    """Called by SortableJS when a card is dropped. Body: status=<column>&position=<index>."""
    task = get_task(request.user, project_pk, pk)
    status = request.POST.get("status", "")
    try:
        position = int(request.POST.get("position", ""))
    except ValueError:
        return HttpResponseBadRequest("position must be an integer")
    if status not in Task.Status.values or position < 0:
        return HttpResponseBadRequest("invalid status or position")

    services.move_task(task, status=status, position=position)
    response = HttpResponse(status=204)
    response["HX-Trigger"] = "boardChanged"
    return response
