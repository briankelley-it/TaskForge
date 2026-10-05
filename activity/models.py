from django.conf import settings
from django.db import models


class Activity(models.Model):
    """One line in a project's activity feed, e.g. "Ada moved “Fix login” from To Do to Done"."""

    class Verb(models.TextChoices):
        CREATED = "created", "created"
        UPDATED = "updated", "updated"
        MOVED = "moved", "moved"
        ASSIGNED = "assigned", "assigned"
        COMMENTED = "commented", "commented on"
        DELETED = "deleted", "deleted"

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="activities"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    verb = models.CharField(max_length=20, choices=Verb.choices)
    target_task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities",
    )
    # Copied at the time of the event, so the feed still reads well after the task
    # is renamed or deleted.
    target_title = models.CharField(max_length=200, blank=True)
    detail = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name_plural = "activities"
        indexes = [models.Index(fields=["project", "-created_at"], name="activity_feed_idx")]

    def __str__(self) -> str:
        actor = self.actor or "Someone"
        return f"{actor} {self.get_verb_display()} “{self.target_title}”"
