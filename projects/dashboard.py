"""Everything the dashboard shows, gathered in a fixed number of queries.

Kept out of the view so the view stays thin and this can be tested on its own:
  1. the user's projects, with per-status task counts
  2. their members (one prefetch for every project)
  3. the user's own memberships (stars, last viewed)
  4. open tasks due this week
  5. the user's open tasks
"""

import datetime
from dataclasses import dataclass, field

from django.db.models import Count, F, Q
from django.urls import reverse
from django.utils import timezone

from tasks.models import Task

from .models import Membership, Project

VIEWS = {
    "all": "All projects",
    "owned": "Created by me",
    "shared": "Shared with me",
    "starred": "Starred",
}


@dataclass
class Summary:
    """One of the four small cards at the top of the dashboard."""

    title: str
    count: int
    caption: str
    people: list
    url: str


@dataclass
class Dashboard:
    projects: list
    summaries: list[Summary]
    team: list
    starred: list
    recent: list
    view: str
    view_label: str
    grid: list = field(default_factory=list)
    invite_project: Project | None = None


def annotate_projects(queryset):
    """Per-status task counts. Distinct, because joining members and tasks multiplies rows."""
    s = Task.Status
    return queryset.annotate(
        member_count=Count("memberships", distinct=True),
        todo_count=Count("tasks", filter=Q(tasks__status=s.TODO), distinct=True),
        in_progress_count=Count("tasks", filter=Q(tasks__status=s.IN_PROGRESS), distinct=True),
        done_count=Count("tasks", filter=Q(tasks__status=s.DONE), distinct=True),
    )


def decorate(projects: list, memberships: dict) -> None:
    """Attach the user's membership and a total task count to each project."""
    for project in projects:
        project.my_membership = memberships.get(project.pk)
        project.is_starred = bool(project.my_membership and project.my_membership.is_starred)
        project.task_total = project.todo_count + project.in_progress_count + project.done_count


def build_dashboard(user, view: str = "all") -> Dashboard:
    view = view if view in VIEWS else "all"
    projects = list(
        annotate_projects(Project.objects.for_user(user))
        .select_related("owner")
        .prefetch_related("members")
    )
    memberships = {
        m.project_id: m
        for m in Membership.objects.filter(user=user).only(
            "project_id", "is_starred", "last_viewed_at", "role"
        )
    }
    decorate(projects, memberships)

    owned = [p for p in projects if p.owner_id == user.pk]
    shared = [p for p in projects if p.owner_id != user.pk]
    starred = [p for p in projects if p.is_starred]

    def people(project_list, exclude_self=True):
        seen = {}
        for project in project_list:
            for member in project.members.all():
                if not (exclude_self and member.pk == user.pk):
                    seen.setdefault(member.pk, member)
        return list(seen.values())

    project_ids = [p.pk for p in projects]
    today = timezone.localdate()
    open_tasks = Task.objects.filter(project_id__in=project_ids).exclude(status=Task.Status.DONE)
    due_soon = list(
        open_tasks.filter(due_date__lte=today + datetime.timedelta(days=7)).select_related(
            "assignee"
        )
    )
    mine = list(open_tasks.filter(assignee=user).values_list("project_id", flat=True))

    def assignees(tasks):
        seen = {}
        for task in tasks:
            if task.assignee:
                seen.setdefault(task.assignee_id, task.assignee)
        return list(seen.values())

    my_tasks_url = reverse("my_tasks")
    dashboard_url = reverse("projects:dashboard")
    summaries = [
        Summary(
            "Created projects",
            len(owned),
            plural(len(owned), "project"),
            people(owned),
            f"{dashboard_url}?view=owned#all-projects",
        ),
        Summary(
            "Shared with me",
            len(shared),
            plural(len(shared), "project"),
            [p.owner for p in shared],
            f"{dashboard_url}?view=shared#all-projects",
        ),
        Summary(
            "Due this week",
            len(due_soon),
            plural(len(due_soon), "open task"),
            assignees(due_soon),
            f"{my_tasks_url}?due=week&everyone=1",
        ),
        Summary(
            "My open tasks",
            len(mine),
            f"across {plural(len(set(mine)), 'project')}",
            [user] if mine else [],
            my_tasks_url,
        ),
    ]

    # "Recently viewed": projects opened before, newest first, topped up with the most
    # recently updated ones so the row is never half empty.
    viewed = sorted(
        (p for p in projects if p.my_membership and p.my_membership.last_viewed_at),
        key=lambda p: p.my_membership.last_viewed_at,
        reverse=True,
    )
    recent = (viewed + [p for p in projects if p not in viewed])[:4]

    grid = {"all": projects, "owned": owned, "shared": shared, "starred": starred}[view]
    # Starred first, then most recently updated (the queryset's default order).
    grid = sorted(grid, key=lambda p: not p.is_starred)

    return Dashboard(
        projects=projects,
        summaries=summaries,
        team=people(projects),
        starred=starred,
        recent=recent,
        view=view,
        view_label=VIEWS[view],
        grid=grid,
        invite_project=owned[0] if owned else None,
    )


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def sidebar_memberships(user, limit: int = 5) -> list[Membership]:
    """The coloured project avatars in the sidebar: most recently opened first."""
    return list(
        Membership.objects.filter(user=user)
        .select_related("project")
        .order_by(F("last_viewed_at").desc(nulls_last=True), "-joined_at")[:limit]
    )
