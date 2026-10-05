"""Business logic for tasks: creating them and moving them around the board.

Positions are kept contiguous (0, 1, 2, ...) within each column. Renumbering the
whole column on every move is simple and correct, and a column on a small team's
board holds tens of tasks, not thousands.
"""

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from projects.models import Project

from .models import Task


def _next_position(project: Project, status: str) -> int:
    """Position one past the bottom of a column."""
    top = Task.objects.filter(project=project, status=status).aggregate(m=Max("position"))["m"]
    return 0 if top is None else top + 1


def create_task(*, project: Project, created_by, **fields) -> Task:
    """Create a task at the bottom of its column."""
    status = fields.pop("status", Task.Status.TODO)
    return Task.objects.create(
        project=project,
        created_by=created_by,
        status=status,
        position=_next_position(project, status),
        **fields,
    )


def update_task(task: Task, **fields) -> Task:
    """Save edits from the task form. Changing the status moves the task to the bottom
    of its new column, like dragging it there."""
    # Read the stored status: a bound ModelForm has already copied the new one onto `task`.
    old_status = Task.objects.values_list("status", flat=True).get(pk=task.pk)
    for name, value in fields.items():
        setattr(task, name, value)
    with transaction.atomic():
        if task.status != old_status:
            task.position = _next_position(task.project, task.status)
        task.save()
        if task.status != old_status:
            _renumber(task.project, old_status)
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
def move_task(task: Task, *, status: str, position: int) -> bool:
    """Move a task to `position` (0 = top) in the `status` column.

    Returns True if the task changed column, which the activity feed uses.
    Rows are locked so two people dragging at once can't end up with duplicate
    positions.
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

    if old_status != status:
        _renumber(task.project, old_status)
    return old_status != status


@transaction.atomic
def delete_task(task: Task) -> None:
    project, status = task.project, task.status
    task.delete()
    _renumber(project, status)
