"""Phase 5: CSV export, due-soon badges, the 'ago' filter, dark mode and seed_demo."""

import csv
import datetime
import io

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains

from accounts.models import User
from activity.models import Activity
from projects.management.commands.seed_demo import DEFAULT_PASSWORD, DEMO_EMAIL
from projects.models import Project
from projects.templatetags.taskforge import ago
from tasks.models import Comment, Task
from tests.factories import TaskFactory

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()


def days(n: int) -> datetime.date:
    return TODAY + datetime.timedelta(days=n)


class TestCsvExport:
    def url(self, project):
        return reverse("tasks:export_csv", args=[project.pk])

    def rows(self, response) -> list[dict]:
        return list(csv.DictReader(io.StringIO(response.content.decode())))

    def test_downloads_all_tasks(self, logged_in_client, project, user):
        TaskFactory(project=project, title="Plan", assignee=user, due_date=days(3))
        TaskFactory(project=project, title="Ship", status=Task.Status.DONE)

        response = logged_in_client.get(self.url(project))

        assert response["Content-Type"].startswith("text/csv")
        assert "attachment;" in response["Content-Disposition"]
        assert (
            f"{project.name.lower().replace(' ', '-')}-tasks.csv" in response["Content-Disposition"]
        )
        rows = self.rows(response)
        assert [r["Title"] for r in rows] == ["Plan", "Ship"]
        assert rows[0]["Assignee"] == user.email
        assert rows[0]["Due date"] == days(3).isoformat()
        assert rows[1]["Status"] == "Done"

    def test_respects_board_filters(self, logged_in_client, project):
        TaskFactory(project=project, title="Fix login", priority="high")
        TaskFactory(project=project, title="Write docs", priority="low")
        response = logged_in_client.get(self.url(project), {"priority": "high"})
        assert [r["Title"] for r in self.rows(response)] == ["Fix login"]

    def test_board_links_to_export_with_current_filters(self, logged_in_client, project):
        response = logged_in_client.get(
            project.get_absolute_url(), {"q": "x"}, HTTP_HX_REQUEST="true"
        )
        # The board partial re-sends the export button out of band with the new filters.
        assertContains(response, 'hx-swap-oob="true"')
        assertContains(response, f"{self.url(project)}?q=x")


class TestDueSoon:
    @pytest.mark.parametrize(
        "due_in,status,expected",
        [
            (0, Task.Status.TODO, True),
            (2, Task.Status.IN_PROGRESS, True),
            (3, Task.Status.TODO, False),
            (-1, Task.Status.TODO, False),  # overdue, not "soon"
            (1, Task.Status.DONE, False),
        ],
    )
    def test_is_due_soon(self, due_in, status, expected):
        assert TaskFactory(due_date=days(due_in), status=status).is_due_soon is expected

    def test_no_due_date(self):
        assert TaskFactory(due_date=None).is_due_soon is False

    def test_board_shows_badges(self, logged_in_client, project):
        TaskFactory(project=project, due_date=days(1))
        TaskFactory(project=project, due_date=days(-1))
        response = logged_in_client.get(project.get_absolute_url())
        assertContains(response, "Due soon ·")
        assertContains(response, "Overdue ·")


class TestAgoFilter:
    def test_just_now(self):
        assert ago(timezone.now()) == "just now"

    def test_older(self):
        assert (
            ago(timezone.now() - datetime.timedelta(hours=3, minutes=5)) == "3 hours ago"
        )  # timesince uses a non-breaking space

    def test_empty(self):
        assert ago(None) == ""


def test_dark_mode_toggle_and_no_flash_script_are_on_every_page(client):
    response = client.get(reverse("account_signup"))
    assertContains(response, "data-theme-toggle")
    assertContains(response, 'localStorage.getItem("theme")')


class TestSeedDemo:
    def test_creates_demo_user_projects_and_tasks(self):
        call_command("seed_demo", stdout=io.StringIO())

        demo = User.objects.get(email=DEMO_EMAIL)
        assert demo.check_password(DEFAULT_PASSWORD)
        projects = Project.objects.filter(owner=demo)
        assert projects.count() == 2
        assert all(p.memberships.count() == 3 for p in projects)
        assert 18 <= Task.objects.filter(project__in=projects).count() <= 22
        # Every column is used, and some tasks are overdue, so the demo looks lived-in.
        statuses = set(Task.objects.values_list("status", flat=True))
        assert statuses == set(Task.Status.values)
        assert any(t.is_overdue for t in Task.objects.all())
        assert Comment.objects.exists()
        assert Activity.objects.filter(verb=Activity.Verb.MOVED).exists()

    def test_positions_are_contiguous_in_every_column(self):
        call_command("seed_demo", stdout=io.StringIO())
        for project in Project.objects.all():
            for status in Task.Status.values:
                positions = list(
                    project.tasks.filter(status=status)
                    .order_by("position")
                    .values_list("position", flat=True)
                )
                assert positions == list(range(len(positions)))

    def test_running_twice_resets_instead_of_duplicating(self):
        call_command("seed_demo", stdout=io.StringIO())
        first_count = Task.objects.count()
        call_command("seed_demo", "--password", "new-pass-123", stdout=io.StringIO())

        assert Project.objects.count() == 2
        assert Task.objects.count() == first_count
        assert User.objects.get(email=DEMO_EMAIL).check_password("new-pass-123")

    def test_prints_login_details(self):
        out = io.StringIO()
        call_command("seed_demo", stdout=out)
        assert DEMO_EMAIL in out.getvalue()


def test_seed_demo_if_missing_only_runs_once():
    call_command("seed_demo", "--if-missing", stdout=io.StringIO())
    first = set(Task.objects.values_list("pk", flat=True))
    out = io.StringIO()
    call_command("seed_demo", "--if-missing", stdout=out)
    assert "already exists" in out.getvalue()
    assert set(Task.objects.values_list("pk", flat=True)) == first
