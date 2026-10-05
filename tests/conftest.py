import pytest

from tests.factories import UserFactory


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def logged_in_client(client, user):
    client.force_login(user)
    return client
