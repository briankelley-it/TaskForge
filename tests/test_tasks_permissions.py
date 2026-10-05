"""Every task URL: logged-out users go to login, non-members get 404, and a task can't
be reached through a different project's URL."""

import pytest
from django.urls import reverse

from tasks.models import Task
from tests.factories import MembershipFactory, TaskFactory

pytestmark = pytest.mark.django_db

# (url name, HTTP method, needs a task id)
TASK_URLS = [
    ("tasks:board", "get", False),
    ("tasks:create", "get", False),
    ("tasks:create", "post", False),
    ("tasks:export_csv", "get", False),
    ("tasks:detail", "get", True),
    ("tasks:update", "get", True),
    ("tasks:update", "post", True),
    ("tasks:delete", "post", True),
    ("tasks:move", "post", True),
    ("tasks:comment_create", "post", True),
]


@pytest.fixture
def task(project):
    return TaskFactory(project=project, title="Secret")


def build_url(name, project_pk, task, needs_task):
    return reverse(name, args=[project_pk, task.pk] if needs_task else [project_pk])


@pytest.mark.parametrize("name,method,needs_task", TASK_URLS)
def test_logged_out_user_is_redirected_to_login(client, task, name, method, needs_task):
    response = getattr(client, method)(build_url(name, task.project_id, task, needs_task))
    assert response.status_code == 302
    assert response.url.startswith(reverse("account_login"))


@pytest.mark.parametrize("name,method,needs_task", TASK_URLS)
def test_non_member_gets_404(client, outsider, task, name, method, needs_task):
    client.force_login(outsider)
    data = {"title": "Hacked", "status": "done", "priority": "low", "position": "0", "body": "x"}
    response = getattr(client, method)(build_url(name, task.project_id, task, needs_task), data)
    assert response.status_code == 404
    task.refresh_from_db()
    assert (task.title, task.status) == ("Secret", "todo")
    assert not task.comments.exists()


@pytest.mark.parametrize("name,method", [(n, m) for n, m, needs_task in TASK_URLS if needs_task])
def test_task_from_another_project_is_404(client, task, name, method):
    """Being a member of project B doesn't give access to project A's tasks via B's URL."""
    other = MembershipFactory()
    client.force_login(other.user)
    response = getattr(client, method)(reverse(name, args=[other.project_id, task.pk]))
    assert response.status_code == 404
    assert Task.objects.filter(pk=task.pk).exists()
