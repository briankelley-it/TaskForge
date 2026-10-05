import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError

from projects.models import Membership, Project
from tests.factories import MembershipFactory, ProjectFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_project_str_and_url():
    project = ProjectFactory(name="Website relaunch")
    assert str(project) == "Website relaunch"
    assert project.get_absolute_url() == f"/projects/{project.pk}/"


def test_project_factory_creates_owner_membership():
    project = ProjectFactory()
    membership = Membership.objects.get(project=project)
    assert membership.user == project.owner
    assert membership.is_owner


def test_membership_str():
    user = UserFactory(display_name="Ada")
    membership = MembershipFactory(user=user, project=ProjectFactory(name="Apollo"))
    assert str(membership) == "Ada in Apollo (Member)"


def test_role_choices():
    assert Membership.Role.values == ["owner", "member"]
    assert MembershipFactory().role == Membership.Role.MEMBER


def test_user_can_only_join_a_project_once():
    membership = MembershipFactory()
    with pytest.raises(IntegrityError):
        MembershipFactory(project=membership.project, user=membership.user)


def test_deleting_a_project_deletes_its_memberships():
    project = ProjectFactory()
    MembershipFactory(project=project)
    project.delete()
    assert Membership.objects.count() == 0


def test_owner_cannot_be_deleted_while_owning_a_project():
    project = ProjectFactory()
    with pytest.raises(ProtectedError):
        project.owner.delete()


def test_for_user_returns_only_member_projects():
    user = UserFactory()
    owned = ProjectFactory(owner=user)
    joined = MembershipFactory(user=user).project
    ProjectFactory()  # someone else's project

    assert set(Project.objects.for_user(user)) == {owned, joined}


def test_projects_are_ordered_by_most_recently_updated():
    older, newer = ProjectFactory(), ProjectFactory()
    assert list(Project.objects.all()) == [newer, older]
    older.save()  # touches updated_at
    assert list(Project.objects.all()) == [older, newer]
