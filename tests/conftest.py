import pytest

from tests.factories import MembershipFactory, ProjectFactory, UserFactory


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def logged_in_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def project(user):
    """A project owned by `user`."""
    return ProjectFactory(owner=user)


@pytest.fixture
def member(project):
    """A non-owner member of `project`."""
    return MembershipFactory(project=project).user


@pytest.fixture
def outsider(db):
    """A logged-in user with no access to `project`."""
    return UserFactory()


@pytest.fixture
def htmx():
    """Extra request kwargs that make the test client look like HTMX."""
    return {"HTTP_HX_REQUEST": "true"}
