"""Recording activity. Called from the task services, not from views, so every way of
changing a task (board, form, admin action, management command) is logged the same."""

from projects.models import Project

from .models import Activity


def log(
    *,
    project: Project,
    actor,
    verb: Activity.Verb,
    task=None,
    detail: str = "",
) -> Activity:
    return Activity.objects.create(
        project=project,
        actor=actor,
        verb=verb,
        target_task=task,
        target_title=task.title if task else "",
        detail=detail,
    )
