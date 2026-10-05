import pytest
from django.urls import reverse
from pytest_django.asserts import assertContains

from activity.models import Activity
from tasks import services
from tasks.models import Task
from tests.factories import MembershipFactory, TaskFactory, UserFactory

pytestmark = pytest.mark.django_db

Verb = Activity.Verb


def feed(project) -> list[tuple]:
    """(verb, title, detail), oldest first."""
    return list(
        Activity.objects.filter(project=project)
        .order_by("created_at", "id")
        .values_list("verb", "target_title", "detail")
    )


class TestLoggedByServices:
    def test_create(self, project, user):
        services.create_task(project=project, created_by=user, title="Plan")
        assert feed(project) == [(Verb.CREATED, "Plan", "")]
        assert Activity.objects.get().actor == user

    def test_create_with_assignee_also_logs_assignment(self, project, user):
        services.create_task(project=project, created_by=user, title="Plan", assignee=user)
        assert feed(project) == [
            (Verb.CREATED, "Plan", ""),
            (Verb.ASSIGNED, "Plan", f"to {user.name}"),
        ]

    def test_move_to_another_column(self, project, user):
        task = TaskFactory(project=project, title="Plan")
        services.move_task(task, status=Task.Status.DONE, position=0, actor=user)
        assert feed(project) == [(Verb.MOVED, "Plan", "from To Do to Done")]

    def test_reordering_within_a_column_is_not_logged(self, project, user):
        task = TaskFactory(project=project)
        TaskFactory(project=project)
        services.move_task(task, status=Task.Status.TODO, position=1, actor=user)
        assert feed(project) == []

    def test_form_edit_that_changes_status_and_assignee(self, project, user, member):
        task = TaskFactory(project=project, title="Plan")
        services.update_task(task, actor=user, status=Task.Status.IN_PROGRESS, assignee=member)
        assert feed(project) == [
            (Verb.MOVED, "Plan", "from To Do to In Progress"),
            (Verb.ASSIGNED, "Plan", f"to {member.name}"),
        ]

    def test_unassigning(self, project, user):
        task = TaskFactory(project=project, title="Plan", assignee=user)
        services.update_task(task, actor=user, assignee=None)
        assert feed(project) == [(Verb.ASSIGNED, "Plan", "to nobody")]

    def test_plain_edit_logs_updated(self, project, user):
        task = TaskFactory(project=project, title="Plan")
        services.update_task(task, actor=user, title="Better plan")
        assert feed(project) == [(Verb.UPDATED, "Better plan", "")]

    def test_comment(self, project, user):
        task = TaskFactory(project=project, title="Plan")
        services.add_comment(task, author=user, body="Hi")
        assert feed(project) == [(Verb.COMMENTED, "Plan", "")]

    def test_delete_keeps_title_after_task_is_gone(self, project, user):
        task = TaskFactory(project=project, title="Old idea")
        services.delete_task(task, actor=user)
        entry = Activity.objects.get()
        assert (entry.verb, entry.target_title, entry.target_task) == (
            Verb.DELETED,
            "Old idea",
            None,
        )


def test_str(project):
    actor = UserFactory(display_name="Ada")
    task = TaskFactory(project=project, title="Plan")
    services.move_task(task, status=Task.Status.DONE, position=0, actor=actor)
    assert str(Activity.objects.get()) == "Ada moved “Plan”"


def test_str_without_actor(project):
    entry = Activity.objects.create(project=project, verb=Verb.DELETED, target_title="X")
    assert str(entry) == "Someone deleted “X”"


def test_views_record_activity_end_to_end(logged_in_client, project, htmx):
    task = TaskFactory(project=project, title="Plan")
    logged_in_client.post(
        reverse("tasks:move", args=[project.pk, task.pk]),
        {"status": "in_progress", "position": "0"},
        **htmx,
    )
    logged_in_client.post(
        reverse("tasks:comment_create", args=[project.pk, task.pk]), {"body": "Hi"}, **htmx
    )
    assert [v for v, _, _ in feed(project)] == [Verb.MOVED, Verb.COMMENTED]


class TestFeedPage:
    def url(self, project):
        return reverse("activity:feed", args=[project.pk])

    def test_lists_newest_first_with_links(self, logged_in_client, project, user):
        task = TaskFactory(project=project, title="Plan")
        services.move_task(task, status=Task.Status.DONE, position=0, actor=user)
        services.add_comment(task, author=user, body="Done!")

        response = logged_in_client.get(self.url(project))

        verbs = [a.verb for a in response.context["activities"]]
        assert verbs == [Verb.COMMENTED, Verb.MOVED]
        assertContains(response, "from To Do to Done")
        assertContains(response, task.get_absolute_url())

    def test_only_this_projects_activity(self, logged_in_client, project):
        other = MembershipFactory().project
        TaskFactory(project=other)
        services.create_task(project=other, created_by=other.owner, title="Elsewhere")
        response = logged_in_client.get(self.url(project))
        assert list(response.context["activities"]) == []
        assertContains(response, "Nothing has happened yet")

    def test_paginates(self, logged_in_client, project, user):
        task = TaskFactory(project=project)
        for _ in range(35):
            services.add_comment(task, author=user, body="x")
        response = logged_in_client.get(self.url(project))
        assert len(response.context["activities"]) == 30
        assert response.context["is_paginated"]
        assert len(logged_in_client.get(self.url(project), {"page": 2}).context["activities"]) == 5

    def test_query_count_does_not_grow(
        self, logged_in_client, project, user, django_assert_num_queries
    ):
        task = TaskFactory(project=project)
        services.add_comment(task, author=user, body="x")
        # session, user, membership, count (paginator), activities (+actor, task)
        with django_assert_num_queries(5):
            logged_in_client.get(self.url(project))
        for _ in range(10):
            services.add_comment(task, author=user, body="x")
        with django_assert_num_queries(5):
            logged_in_client.get(self.url(project))

    def test_logged_out_redirects(self, client, project):
        response = client.get(self.url(project))
        assert response.status_code == 302
        assert response.url.startswith(reverse("account_login"))

    def test_non_member_gets_404(self, client, project, outsider):
        client.force_login(outsider)
        assert client.get(self.url(project)).status_code == 404

    def test_member_can_view(self, client, project, member):
        client.force_login(member)
        assert client.get(self.url(project)).status_code == 200


def test_admin_pages_render(admin_client, project, user):
    task = TaskFactory(project=project)
    services.add_comment(task, author=user, body="x")
    for name in ["admin:activity_activity_changelist", "admin:tasks_comment_changelist"]:
        assert admin_client.get(reverse(name)).status_code == 200
    entry = Activity.objects.get()
    assert (
        admin_client.get(reverse("admin:activity_activity_change", args=[entry.pk])).status_code
        == 200
    )
    assert admin_client.get(reverse("admin:activity_activity_add")).status_code == 403
