import pytest

from projects import services
from projects.models import Membership
from tests.factories import MembershipFactory, ProjectFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_create_project_makes_creator_the_owner():
    user = UserFactory()
    project = services.create_project(owner=user, name="Apollo", description="To the moon")

    assert project.owner == user
    membership = Membership.objects.get(project=project)
    assert membership.user == user
    assert membership.role == Membership.Role.OWNER


def test_invite_existing_user_adds_member():
    project = ProjectFactory()
    invitee = UserFactory(email="grace@example.com")

    result, user = services.invite_member(project=project, email="grace@example.com")

    assert result == services.InviteResult.ADDED
    assert user == invitee
    assert Membership.objects.get(project=project, user=invitee).role == Membership.Role.MEMBER


def test_invite_matches_email_case_insensitively():
    project = ProjectFactory()
    UserFactory(email="grace@example.com")

    result, _ = services.invite_member(project=project, email="  GRACE@Example.com ")

    assert result == services.InviteResult.ADDED


def test_invite_existing_member_is_reported_and_not_duplicated():
    membership = MembershipFactory()

    result, _ = services.invite_member(project=membership.project, email=membership.user.email)

    assert result == services.InviteResult.ALREADY_MEMBER
    assert Membership.objects.filter(project=membership.project).count() == 2


def test_invite_unknown_email_adds_nobody():
    project = ProjectFactory()

    result, user = services.invite_member(project=project, email="nobody@example.com")

    assert result == services.InviteResult.NO_SUCH_USER
    assert user is None
    assert project.memberships.count() == 1


def test_remove_member():
    membership = MembershipFactory()
    services.remove_member(project=membership.project, user=membership.user)
    assert not Membership.objects.filter(pk=membership.pk).exists()


def test_owner_cannot_be_removed():
    project = ProjectFactory()
    with pytest.raises(services.CannotRemoveOwner):
        services.remove_member(project=project, user=project.owner)
    assert project.memberships.filter(user=project.owner).exists()
