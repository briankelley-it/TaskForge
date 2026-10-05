import pytest
from django.urls import reverse
from pytest_django.asserts import assertContains, assertRedirects, assertTemplateUsed

from tasks.forms import CommentForm
from tasks.models import Comment
from tests.factories import CommentFactory, TaskFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def task(project):
    return TaskFactory(project=project, title="Fix login")


def comment_url(task):
    return reverse("tasks:comment_create", args=[task.project_id, task.pk])


def test_comment_str_and_ordering(task):
    author = UserFactory(display_name="Ada")
    second = CommentFactory(task=task, author=author)
    first = CommentFactory(task=task, author=author)
    first.created_at, second.created_at = second.created_at, first.created_at
    Comment.objects.bulk_update([first, second], ["created_at"])

    assert str(first) == "Comment by Ada on Fix login"
    assert list(task.comments.all()) == [first, second]


def test_deleting_author_keeps_comment(task, member):
    comment = CommentFactory(task=task, author=member)
    member.delete()
    comment.refresh_from_db()
    assert comment.author is None
    assert "deleted user" in str(comment)


class TestTaskDetail:
    def test_htmx_returns_modal_with_comments(self, logged_in_client, task, htmx):
        CommentFactory(task=task, body="Looks good to me")
        response = logged_in_client.get(task.get_absolute_url(), **htmx)
        assertTemplateUsed(response, "tasks/partials/task_detail.html")
        assertContains(response, 'role="dialog"')
        assertContains(response, "Looks good to me")
        assertContains(response, task.get_edit_url())

    def test_plain_request_renders_full_page(self, logged_in_client, task):
        response = logged_in_client.get(task.get_absolute_url())
        assertTemplateUsed(response, "tasks/task_detail.html")

    def test_detail_query_count_does_not_grow_with_comments(
        self, logged_in_client, task, htmx, django_assert_num_queries
    ):
        CommentFactory.create_batch(2, task=task)
        with django_assert_num_queries(5):  # session, user, membership, task, comments
            logged_in_client.get(task.get_absolute_url(), **htmx)
        CommentFactory.create_batch(10, task=task)
        with django_assert_num_queries(5):
            logged_in_client.get(task.get_absolute_url(), **htmx)


class TestAddComment:
    def test_htmx_post_adds_comment_and_returns_thread(self, logged_in_client, task, user, htmx):
        response = logged_in_client.post(comment_url(task), {"body": "  On it!  "}, **htmx)

        assert response.status_code == 200
        assertTemplateUsed(response, "tasks/partials/comments.html")
        assertContains(response, "On it!")
        assert response["HX-Trigger"] == "boardChanged"
        comment = Comment.objects.get()
        assert (comment.task, comment.author, comment.body) == (task, user, "On it!")

    def test_blank_comment_shows_error(self, logged_in_client, task, htmx):
        response = logged_in_client.post(comment_url(task), {"body": "   "}, **htmx)
        assert response.status_code == 200
        assertContains(response, "This field is required")
        assert "HX-Trigger" not in response
        assert not Comment.objects.exists()

    def test_plain_post_redirects_to_task(self, logged_in_client, task):
        response = logged_in_client.post(comment_url(task), {"body": "Plain"})
        assertRedirects(response, task.get_absolute_url())

    def test_plain_invalid_post_shows_task_page_with_error(self, logged_in_client, task):
        response = logged_in_client.post(comment_url(task), {"body": ""})
        assertTemplateUsed(response, "tasks/task_detail.html")
        assert response.context["comment_form"].errors

    def test_any_member_can_comment(self, client, task, member, htmx):
        client.force_login(member)
        response = client.post(comment_url(task), {"body": "Member here"}, **htmx)
        assert response.status_code == 200
        assert Comment.objects.get().author == member

    def test_get_not_allowed(self, logged_in_client, task):
        assert logged_in_client.get(comment_url(task)).status_code == 405


def test_card_shows_comment_count(logged_in_client, task):
    CommentFactory.create_batch(3, task=task)
    response = logged_in_client.get(task.project.get_absolute_url())
    [card] = [t for c in response.context["columns"] for t in c["tasks"]]
    assert card.comment_count == 3
    assertContains(response, "3 comments")


def test_comment_form_rejects_whitespace_only():
    form = CommentForm({"body": "\n  \t"})
    assert not form.is_valid()
