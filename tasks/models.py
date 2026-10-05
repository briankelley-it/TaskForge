from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from projects.models import Project


class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "todo", "To Do"
        IN_PROGRESS = "in_progress", "In Progress"
        DONE = "done", "Done"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    due_date = models.DateField(null=True, blank=True)
    # SET_NULL: if someone leaves TaskForge, their tasks stay and become unassigned.
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
    )
    # Order within a column, 0 at the top. Kept contiguous by tasks.services.
    position = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "position", "id"]
        # The board loads one project's tasks column by column, in position order.
        indexes = [
            models.Index(fields=["project", "status", "position"], name="task_board_order_idx"),
            models.Index(fields=["assignee"], name="task_assignee_idx"),
        ]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("tasks:detail", kwargs={"project_pk": self.project_id, "pk": self.pk})

    def get_edit_url(self) -> str:
        return reverse("tasks:update", kwargs={"project_pk": self.project_id, "pk": self.pk})

    @property
    def is_overdue(self) -> bool:
        return (
            self.due_date is not None
            and self.status != self.Status.DONE
            and self.due_date < timezone.localdate()
        )


class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    # SET_NULL keeps the conversation readable if a commenter deletes their account.
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="comments"
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["task", "created_at"], name="comment_task_idx")]

    def __str__(self) -> str:
        return f"Comment by {self.author or 'deleted user'} on {self.task}"
