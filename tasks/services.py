"""Business logic for tasks: creating, editing, moving and commenting, plus the activity
each of those records.

Positions are kept contiguous (0, 1, 2, ...) within each column. Renumbering the
whole column on every move is simple and correct, and a column on a small team's
board holds tens of tasks, not thousands.
"""

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from activity import services as activity
from activity.models import Activity
from projects.models import Project

from .models import Comment, Task

Verb = Activity.Verb


def _next_position(project: Project, status: str) -> int:
    """Position one past the bottom of a column."""
    top = Task.objects.filter(project=project, status=status).aggregate(m=Max("position"))["m"]
    return 0 if top is None else top + 1


def _moved_detail(old_status: str, new_status: str) -> str:
    return f"from {Task.Status(old_status).label} to {Task.Status(new_status).label}"


@transaction.atomic
def create_task(*, project: Project, created_by, **fields) -> Task:
    """Create a task at the bottom of its column."""
    status = fields.pop("status", Task.Status.TODO)
    task = Task.objects.create(
        project=project,
        created_by=created_by,
        status=status,
        position=_next_position(project, status),
        **fields,
    )
    activity.log(project=project, actor=created_by, verb=Verb.CREATED, task=task)
    if task.assignee:
        _log_assigned(task, created_by)
    return task


def _log_assigned(task: Task, actor) -> None:
    detail = f"to {task.assignee.name}" if task.assignee else "to nobody"
    activity.log(project=task.project, actor=actor, verb=Verb.ASSIGNED, task=task, detail=detail)


@transaction.atomic
def update_task(task: Task, *, actor, **fields) -> Task:
    """Save edits from the task form. Changing the status moves the task to the bottom
    of its new column, like dragging it there."""
    # Read the stored values: a bound ModelForm has already copied the new ones onto `task`.
    old_status, old_assignee_id = Task.objects.values_list("status", "assignee_id").get(pk=task.pk)
    for name, value in fields.items():
        setattr(task, name, value)

    moved = task.status != old_status
    if moved:
        task.position = _next_position(task.project, task.status)
    task.save()
    if moved:
        _renumber(task.project, old_status)

    # One feed line per meaningful change; plain edits get a single "updated" line.
    if moved:
        activity.log(
            project=task.project,
            actor=actor,
            verb=Verb.MOVED,
            task=task,
            detail=_moved_detail(old_status, task.status),
        )
    if task.assignee_id != old_assignee_id:
        _log_assigned(task, actor)
    if not moved and task.assignee_id == old_assignee_id:
        activity.log(project=task.project, actor=actor, verb=Verb.UPDATED, task=task)
    return task


def _renumber(project: Project, status: str) -> None:
    """Close the gaps a task leaves behind when it leaves a column."""
    tasks = list(Task.objects.filter(project=project, status=status).order_by("position", "id"))
    changed = []
    for index, task in enumerate(tasks):
        if task.position != index:
            task.position = index
            changed.append(task)
    Task.objects.bulk_update(changed, ["position"])


@transaction.atomic
def move_task(task: Task, *, status: str, position: int, actor) -> bool:
    """Move a task to `position` (0 = top) in the `status` column.

    Returns True if the task changed column. Only column changes go in the activity
    feed; reordering within a column would just be noise.
    Rows are locked so two people dragging at once can't end up with duplicate positions.
    """
    if status not in Task.Status.values:
        raise ValueError(f"Unknown status: {status!r}")

    # Lock this project's tasks so concurrent moves run one after another.
    list(Task.objects.select_for_update().filter(project=task.project).values_list("pk"))

    old_status = task.status
    column = list(
        Task.objects.filter(project=task.project, status=status)
        .exclude(pk=task.pk)
        .order_by("position", "id")
    )
    position = max(0, min(position, len(column)))
    column.insert(position, task)

    task.status = status
    task.updated_at = timezone.now()
    for index, item in enumerate(column):
        item.position = index
    # bulk_update skips auto_now, so updated_at is set by hand above.
    Task.objects.bulk_update(column, ["status", "position", "updated_at"])

    changed_column = old_status != status
    if changed_column:
        _renumber(task.project, old_status)
        activity.log(
            project=task.project,
            actor=actor,
            verb=Verb.MOVED,
            task=task,
            detail=_moved_detail(old_status, status),
        )
    return changed_column


@transaction.atomic
def delete_task(task: Task, *, actor) -> None:
    project, status = task.project, task.status
    # Logged first so the entry can copy the title; target_task becomes NULL on delete.
    activity.log(project=project, actor=actor, verb=Verb.DELETED, task=task)
    task.delete()
    _renumber(project, status)


@transaction.atomic
def add_comment(task: Task, *, author, body: str) -> Comment:
    comment = Comment.objects.create(task=task, author=author, body=body.strip())
    activity.log(project=task.project, actor=author, verb=Verb.COMMENTED, task=task)
    return comment
