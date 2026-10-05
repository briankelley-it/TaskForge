"""Recording activity. Called from the task services, not from views, so every way of
changing a task (board, form, admin action, management command) is logged the same."""

from django.utils import timezone

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


def notifications_for(user):
    """What other people did in the user's projects, newest first."""
    return (
        Activity.objects.filter(project__in=Project.objects.for_user(user))
        .exclude(actor=user)
        .select_related("actor", "project", "target_task")
    )


def unread_count(user) -> int:
    notifications = notifications_for(user)
    if user.notifications_seen_at:
        notifications = notifications.filter(created_at__gt=user.notifications_seen_at)
    return notifications.count()


def mark_notifications_seen(user) -> None:
    user.notifications_seen_at = timezone.now()
    user.save(update_fields=["notifications_seen_at"])
