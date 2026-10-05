import json

import pytest
from django.urls import reverse
from pytest_django.asserts import assertContains, assertRedirects, assertTemplateUsed

from tasks.models import Task
from tests.factories import MembershipFactory, ProjectFactory, TaskFactory, UserFactory

pytestmark = pytest.mark.django_db


def triggers(response) -> dict:
    return json.loads(response["HX-Trigger"])


class TestBoard:
    def test_shows_tasks_in_their_columns(self, logged_in_client, project):
        TaskFactory(project=project, title="Plan")
        TaskFactory(project=project, title="Build", status=Task.Status.IN_PROGRESS)
        response = logged_in_client.get(project.get_absolute_url())

        assertTemplateUsed(response, "tasks/board.html")
        columns = {c["status"]: [t.title for t in c["tasks"]] for c in response.context["columns"]}
        assert columns == {"todo": ["Plan"], "in_progress": ["Build"], "done": []}
        assertContains(response, reverse("tasks:create", args=[project.pk]))

    def test_htmx_request_returns_only_the_board_partial(self, logged_in_client, project, htmx):
        response = logged_in_client.get(project.get_absolute_url(), **htmx)
        assertTemplateUsed(response, "tasks/partials/board.html")
        assert b"<html" not in response.content
        assert b'hx-trigger="boardChanged from:body"' in response.content

    def test_board_query_count_does_not_grow_with_tasks(
        self, logged_in_client, project, django_assert_num_queries
    ):
        """Guards against N+1 queries: the count stays the same with 1 task or 30."""
        assignee = MembershipFactory(project=project).user
        TaskFactory(project=project, assignee=assignee)
        url = project.get_absolute_url()

        # session, user, membership (+project, owner), tasks (+assignee)
        with django_assert_num_queries(4):
            logged_in_client.get(url)

        for _ in range(29):
            TaskFactory(project=project, assignee=assignee, status=Task.Status.DONE)
        with django_assert_num_queries(4):
            response = logged_in_client.get(url)
        assert sum(len(c["tasks"]) for c in response.context["columns"]) == 30


class TestCreateTask:
    def url(self, project):
        return reverse("tasks:create", args=[project.pk])

    def test_htmx_get_returns_modal_form(self, logged_in_client, project, htmx):
        response = logged_in_client.get(self.url(project), **htmx)
        assertTemplateUsed(response, "tasks/partials/task_form.html")
        assertContains(response, 'role="dialog"')

    def test_column_plus_button_preselects_status(self, logged_in_client, project, htmx):
        response = logged_in_client.get(self.url(project) + "?status=done", **htmx)
        assert response.context["form"].initial["status"] == "done"

    def test_bad_status_param_falls_back_to_todo(self, logged_in_client, project, htmx):
        response = logged_in_client.get(self.url(project) + "?status=nope", **htmx)
        assert response.context["form"].initial["status"] == "todo"

    def test_htmx_post_creates_task_and_triggers_board_refresh(
        self, logged_in_client, project, user, htmx
    ):
        response = logged_in_client.post(
            self.url(project),
            {"title": "Ship it", "status": "todo", "priority": "high", "assignee": user.pk},
            **htmx,
        )
        assert response.status_code == 204
        assert triggers(response) == {"boardChanged": None, "closeModal": None}
        task = Task.objects.get(title="Ship it")
        assert (task.project, task.created_by, task.assignee) == (project, user, user)

    def test_invalid_post_returns_form_with_errors(self, logged_in_client, project, htmx):
        response = logged_in_client.post(
            self.url(project), {"title": "", "status": "todo", "priority": "low"}, **htmx
        )
        assert response.status_code == 200
        assertTemplateUsed(response, "tasks/partials/task_form.html")
        assert response.context["form"].errors["title"]

    def test_cannot_assign_someone_outside_the_project(self, logged_in_client, project, htmx):
        outsider = UserFactory()
        response = logged_in_client.post(
            self.url(project),
            {"title": "X", "status": "todo", "priority": "low", "assignee": outsider.pk},
            **htmx,
        )
        assert response.context["form"].errors["assignee"]
        assert not Task.objects.exists()

    def test_works_without_htmx(self, logged_in_client, project):
        assertTemplateUsed(logged_in_client.get(self.url(project)), "tasks/task_form.html")
        response = logged_in_client.post(
            self.url(project), {"title": "Plain", "status": "todo", "priority": "low"}
        )
        assertRedirects(response, project.get_absolute_url())


class TestUpdateTask:
    def test_htmx_get_prefills_form(self, logged_in_client, project, htmx):
        task = TaskFactory(project=project, title="Old")
        response = logged_in_client.get(task.get_edit_url(), **htmx)
        assertContains(response, 'value="Old"')
        assertContains(response, reverse("tasks:delete", args=[project.pk, task.pk]))

    def test_htmx_post_saves(self, logged_in_client, project, htmx):
        task = TaskFactory(project=project)
        response = logged_in_client.post(
            task.get_edit_url(),
            {"title": "New", "status": "done", "priority": "low", "due_date": "2030-01-31"},
            **htmx,
        )
        assert response.status_code == 204
        task.refresh_from_db()
        assert (task.title, task.status, str(task.due_date)) == ("New", "done", "2030-01-31")

    def test_invalid_post_returns_form(self, logged_in_client, project, htmx):
        task = TaskFactory(project=project)
        response = logged_in_client.post(
            task.get_edit_url(), {"title": "", "status": "x", "priority": "low"}, **htmx
        )
        assert response.status_code == 200
        assert response.context["form"].errors

    def test_plain_get_renders_full_page(self, logged_in_client, project):
        task = TaskFactory(project=project)
        assertTemplateUsed(logged_in_client.get(task.get_edit_url()), "tasks/task_form.html")


class TestDeleteTask:
    def test_htmx_delete(self, logged_in_client, project, htmx):
        task = TaskFactory(project=project)
        response = logged_in_client.post(
            reverse("tasks:delete", args=[project.pk, task.pk]), **htmx
        )
        assert response.status_code == 204
        assert "boardChanged" in triggers(response)
        assert not Task.objects.exists()

    def test_plain_delete_redirects_to_board(self, logged_in_client, project):
        task = TaskFactory(project=project)
        response = logged_in_client.post(reverse("tasks:delete", args=[project.pk, task.pk]))
        assertRedirects(response, project.get_absolute_url())

    def test_get_not_allowed(self, logged_in_client, project):
        task = TaskFactory(project=project)
        url = reverse("tasks:delete", args=[project.pk, task.pk])
        assert logged_in_client.get(url).status_code == 405


class TestMoveTask:
    def url(self, task):
        return reverse("tasks:move", args=[task.project_id, task.pk])

    def test_move_updates_status_and_position(self, logged_in_client, project, htmx):
        first = TaskFactory(project=project, status=Task.Status.DONE)
        task = TaskFactory(project=project)
        response = logged_in_client.post(
            self.url(task), {"status": "done", "position": "0"}, **htmx
        )
        assert response.status_code == 204
        assert response["HX-Trigger"] == "boardChanged"
        task.refresh_from_db()
        first.refresh_from_db()
        assert (task.status, task.position, first.position) == ("done", 0, 1)

    @pytest.mark.parametrize(
        "data",
        [
            {"status": "archived", "position": "0"},
            {"status": "done", "position": "top"},
            {"status": "done", "position": "-1"},
            {"status": "done"},
        ],
    )
    def test_bad_input_is_400(self, logged_in_client, project, data):
        task = TaskFactory(project=project)
        assert logged_in_client.post(self.url(task), data).status_code == 400


def test_member_who_is_not_owner_can_manage_tasks(client, project, member, htmx):
    """Any member can work on tasks; only project settings are owner-only."""
    client.force_login(member)
    response = client.post(
        reverse("tasks:create", args=[project.pk]),
        {"title": "Member task", "status": "todo", "priority": "low"},
        **htmx,
    )
    assert response.status_code == 204
    task = Task.objects.get()
    assert (
        client.post(reverse("tasks:delete", args=[project.pk, task.pk]), **htmx).status_code == 204
    )


def test_dashboard_shows_task_counts_per_status(logged_in_client, project):
    TaskFactory.create_batch(2, project=project)
    TaskFactory(project=project, status=Task.Status.IN_PROGRESS)
    MembershipFactory(project=project)  # extra member must not inflate the task counts
    ProjectFactory()

    response = logged_in_client.get(reverse("projects:dashboard"))
    [row] = response.context["projects"]
    assert (row.todo_count, row.in_progress_count, row.done_count, row.member_count) == (
        2,
        1,
        0,
        2,
    )


def test_task_admin_pages_render(admin_client, project):
    task = TaskFactory(project=project)
    assert admin_client.get(reverse("admin:tasks_task_changelist")).status_code == 200
    assert admin_client.get(reverse("admin:tasks_task_change", args=[task.pk])).status_code == 200


def test_everything_that_opens_the_modal_fills_it_instead_of_replacing_it(
    logged_in_client, project
):
    """Regression: #board's hx-swap="outerHTML" used to be inherited by the cards, so
    opening a task replaced #modal itself and the × button had nothing to close."""
    TaskFactory(project=project)
    html = logged_in_client.get(project.get_absolute_url()).content.decode()
    assert 'hx-disinherit="*"' in html
    opener_count = html.count('hx-target="#modal"')
    assert opener_count >= 3  # "New task", a column "+", a card
    assert html.count('hx-target="#modal" hx-swap="innerHTML"') == opener_count
