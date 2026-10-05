from django.conf import settings
from django.db import models
from django.urls import reverse


class ProjectQuerySet(models.QuerySet["Project"]):
    def for_user(self, user) -> "ProjectQuerySet":
        """Projects the user is a member of.

        Filters with a subquery instead of joining memberships directly, so later
        annotations like Count("memberships") still count every member.
        """
        return self.filter(pk__in=Membership.objects.filter(user=user).values("project_id"))


class Project(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    # PROTECT: deleting a user must not silently delete a project their team relies on.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_projects"
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="Membership", related_name="projects"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProjectQuerySet.as_manager()

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("tasks:board", kwargs={"project_pk": self.pk})


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MEMBER = "member", "Member"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(fields=["project", "user"], name="unique_project_membership"),
        ]
        # The unique constraint already indexes (project, user). This one serves
        # "which projects is this user in?", which runs on every project request.
        indexes = [models.Index(fields=["user", "project"], name="membership_user_project_idx")]

    def __str__(self) -> str:
        return f"{self.user} in {self.project} ({self.get_role_display()})"

    @property
    def is_owner(self) -> bool:
        return self.role == self.Role.OWNER
