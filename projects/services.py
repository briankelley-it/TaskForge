"""Business logic for projects and memberships.

Views call these functions instead of touching the models directly, so the rules
(for example "a project always has an owner membership") live in one place and are
easy to test without HTTP.
"""

from enum import StrEnum

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import Membership, Project

User = get_user_model()


class InviteResult(StrEnum):
    ADDED = "added"
    ALREADY_MEMBER = "already_member"
    NO_SUCH_USER = "no_such_user"


@transaction.atomic
def create_project(*, owner: User, name: str, description: str = "") -> Project:
    """Create a project and make its creator the owner member, together or not at all."""
    project = Project.objects.create(owner=owner, name=name, description=description)
    Membership.objects.create(project=project, user=owner, role=Membership.Role.OWNER)
    return project


def invite_member(*, project: Project, email: str) -> tuple[InviteResult, User | None]:
    """Add an existing user to a project by email.

    TaskForge doesn't send invitation emails yet, so an unknown email is reported
    back to the owner instead of creating a pending invite.
    """
    user = User.objects.filter(email__iexact=email.strip()).first()
    if user is None:
        return InviteResult.NO_SUCH_USER, None
    _, created = Membership.objects.get_or_create(
        project=project, user=user, defaults={"role": Membership.Role.MEMBER}
    )
    return (InviteResult.ADDED if created else InviteResult.ALREADY_MEMBER), user


class CannotRemoveOwner(Exception):
    pass


def remove_member(*, project: Project, user: User) -> None:
    """Remove a member. The owner can't be removed, or the project would be orphaned."""
    membership = Membership.objects.get(project=project, user=user)
    if membership.is_owner:
        raise CannotRemoveOwner("The project owner can't be removed.")
    membership.delete()


def record_view(membership: Membership) -> None:
    """Remember when the user last opened this project, for "Recently viewed"."""
    Membership.objects.filter(pk=membership.pk).update(last_viewed_at=timezone.now())


def toggle_star(membership: Membership) -> bool:
    """Star or unstar a project for this user. Returns the new state."""
    membership.is_starred = not membership.is_starred
    membership.save(update_fields=["is_starred"])
    return membership.is_starred
