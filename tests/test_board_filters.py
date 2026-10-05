import datetime

import pytest
from django.utils import timezone
from pytest_django.asserts import assertContains, assertNotContains, assertTemplateUsed

from tasks.models import Task
from tests.factories import MembershipFactory, TaskFactory

pytestmark = pytest.mark.django_db

YESTERDAY = timezone.localdate() - datetime.timedelta(days=1)
TOMORROW = timezone.localdate() + datetime.timedelta(days=1)


@pytest.fixture
def board(project, user):
    teammate = MembershipFactory(project=project).user
    TaskFactory(project=project, title="Fix login bug", assignee=user, priority="high")
    TaskFactory(project=project, title="Write docs", assignee=teammate, priority="low")
    TaskFactory(project=project, title="Late invoice", due_date=YESTERDAY, priority="medium")
    TaskFactory(project=project, title="Future plan", due_date=TOMORROW, priority="medium")
    TaskFactory(
        project=project,
        title="Done but late",
        due_date=YESTERDAY,
        status=Task.Status.DONE,
        priority="low",
    )
    return project


def titles(response) -> set[str]:
    return {t.title for column in response.context["columns"] for t in column["tasks"]}


def get(client, project, **params):
    return client.get(project.get_absolute_url(), params, HTTP_HX_REQUEST="true")


def test_no_filters_shows_everything(logged_in_client, board):
    response = get(logged_in_client, board)
    assert len(titles(response)) == 5
    assert response.context["filtering"] is False
    assertContains(response, "data-sortable")


def test_search_by_title_is_case_insensitive(logged_in_client, board):
    response = get(logged_in_client, board, q="LOGIN")
    assert titles(response) == {"Fix login bug"}


def test_my_tasks(logged_in_client, board):
    assert titles(get(logged_in_client, board, mine="on")) == {"Fix login bug"}


def test_overdue_excludes_done_and_future_tasks(logged_in_client, board):
    assert titles(get(logged_in_client, board, overdue="on")) == {"Late invoice"}


def test_priority(logged_in_client, board):
    assert titles(get(logged_in_client, board, priority="medium")) == {
        "Late invoice",
        "Future plan",
    }


def test_filters_combine(logged_in_client, board):
    response = get(logged_in_client, board, priority="medium", q="plan")
    assert titles(response) == {"Future plan"}


def test_invalid_priority_is_ignored(logged_in_client, board):
    response = get(logged_in_client, board, priority="urgent", q="docs")
    assert response.status_code == 200
    assert titles(response) == {"Write docs"}


def test_filtering_returns_partial_and_disables_drag_and_drop(logged_in_client, board):
    response = get(logged_in_client, board, q="docs")
    assertTemplateUsed(response, "tasks/partials/board.html")
    assert response.context["filtering"] is True
    assertNotContains(response, "data-sortable")
    assertContains(response, "Drag and drop is paused")


def test_board_refresh_url_keeps_the_filters(logged_in_client, board):
    response = get(logged_in_client, board, q="docs", mine="on")
    assertContains(response, "?q=docs&amp;mine=on")


def test_full_page_load_with_filters_prefills_the_form(logged_in_client, board):
    response = logged_in_client.get(board.get_absolute_url(), {"q": "docs", "overdue": "on"})
    assertTemplateUsed(response, "tasks/board.html")
    assertContains(response, 'value="docs"')
    assert titles(response) == set()


def test_filtered_board_query_count(logged_in_client, board, django_assert_num_queries):
    with django_assert_num_queries(4):
        get(logged_in_client, board, q="a", mine="on", overdue="on", priority="high")
