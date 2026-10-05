import datetime

import pytest
from django.utils import timezone

from tasks.models import Task
from tests.factories import MembershipFactory, TaskFactory

pytestmark = pytest.mark.django_db


def test_str_and_url():
    task = TaskFactory(title="Write README")
    assert str(task) == "Write README"
    assert task.get_absolute_url() == f"/projects/{task.project_id}/tasks/{task.pk}/edit/"


def test_defaults():
    task = TaskFactory()
    assert task.status == Task.Status.TODO
    assert task.priority == Task.Priority.MEDIUM
    assert task.due_date is None
    assert task.assignee is None


def test_choices():
    assert Task.Status.values == ["todo", "in_progress", "done"]
    assert Task.Priority.values == ["low", "medium", "high"]
    assert Task.Status.IN_PROGRESS.label == "In Progress"


def test_is_overdue():
    yesterday = timezone.localdate() - datetime.timedelta(days=1)
    assert TaskFactory(due_date=yesterday).is_overdue
    assert not TaskFactory(due_date=timezone.localdate()).is_overdue
    assert not TaskFactory(due_date=yesterday, status=Task.Status.DONE).is_overdue
    assert not TaskFactory(due_date=None).is_overdue


def test_deleting_assignee_unassigns_task():
    membership = MembershipFactory()
    task = TaskFactory(project=membership.project, assignee=membership.user)
    membership.user.delete()
    task.refresh_from_db()
    assert task.assignee is None


def test_deleting_project_deletes_tasks():
    task = TaskFactory()
    task.project.delete()
    assert not Task.objects.exists()


def test_default_ordering_is_by_column_then_position():
    first = TaskFactory()
    second = TaskFactory(project=first.project)
    assert list(Task.objects.filter(project=first.project)) == [first, second]
