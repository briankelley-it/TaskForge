"""The workspace redesign: dashboard data, stars, recently viewed, search, My tasks,
notifications, avatars and the page shell."""

import datetime

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains, assertNotContains, assertTemplateUsed

from activity import services as activity_services
from projects import services as project_services
from projects.context_processors import nav_active, workspace
from projects.dashboard import build_dashboard, sidebar_memberships
from projects.models import Membership
from tasks import services as task_services
from tasks.models import Task
from tests.factories import MembershipFactory, ProjectFactory, TaskFactory, UserFactory

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()


def days(n: int) -> datetime.date:
    return TODAY + datetime.timedelta(days=n)


def membership(project, user) -> Membership:
    return Membership.objects.get(project=project, user=user)


class TestUserInitials:
    def test_two_words(self):
        assert UserFactory(display_name="Ada Lovelace").initials == "AL"

    def test_one_word_or_email(self):
        assert UserFactory(display_name="Cher").initials == "CH"
        assert UserFactory(display_name="", email="grace@example.com").initials == "GR"


class TestDashboard:
    @pytest.fixture
    def setup(self, user):
        mine = ProjectFactory(owner=user, name="Mine")
        teammate = MembershipFactory(project=mine).user
        shared = MembershipFactory(user=user, project=ProjectFactory(name="Shared")).project
        ProjectFactory(name="Not mine")
        TaskFactory(project=mine, assignee=user, due_date=days(2))
        TaskFactory(project=shared, due_date=days(5), assignee=teammate)
        TaskFactory(project=mine, due_date=days(30))
        TaskFactory(project=mine, due_date=days(1), status=Task.Status.DONE)
        return mine, shared, teammate

    def test_summary_cards(self, user, setup):
        mine, shared, teammate = setup
        d = build_dashboard(user)
        cards = {s.title: s for s in d.summaries}
        assert cards["Created projects"].count == 1
        assert cards["Created projects"].people == [teammate]
        assert cards["Shared with me"].count == 1
        assert cards["Shared with me"].people == [shared.owner]
        # Open tasks due within 7 days, in any of my projects; done tasks don't count.
        assert cards["Due this week"].count == 2
        assert set(cards["Due this week"].people) == {user, teammate}
        assert cards["My open tasks"].count == 1

    def test_team_is_everyone_but_me(self, user, setup):
        mine, shared, teammate = setup
        assert set(build_dashboard(user).team) == {teammate, shared.owner}

    def test_view_filters_the_grid(self, user, setup):
        mine, shared, _ = setup
        assert [p.name for p in build_dashboard(user, "owned").grid] == ["Mine"]
        assert [p.name for p in build_dashboard(user, "shared").grid] == ["Shared"]
        assert build_dashboard(user, "starred").grid == []
        assert build_dashboard(user, "nonsense").view == "all"

    def test_starred_projects_come_first(self, user, setup):
        mine, shared, _ = setup
        project_services.toggle_star(membership(shared, user))
        d = build_dashboard(user)
        assert [p.name for p in d.starred] == ["Shared"]
        assert d.grid[0].name == "Shared"
        assert [p.name for p in build_dashboard(user, "starred").grid] == ["Shared"]

    def test_recently_viewed_puts_opened_projects_first(self, logged_in_client, user, setup):
        mine, shared, _ = setup
        logged_in_client.get(shared.get_absolute_url())
        recent = build_dashboard(user).recent
        assert [p.name for p in recent] == ["Shared", "Mine"]

    def test_invite_goes_to_a_project_i_own(self, user, setup):
        mine, _, _ = setup
        assert build_dashboard(user).invite_project == mine

    def test_task_total(self, user):
        project = ProjectFactory(owner=user)
        TaskFactory.create_batch(2, project=project)
        TaskFactory(project=project, status=Task.Status.DONE)
        [p] = build_dashboard(user).projects
        assert p.task_total == 3

    def test_page_renders(self, logged_in_client, setup):
        response = logged_in_client.get(reverse("projects:dashboard"))
        assertContains(response, "Created projects")
        assertContains(response, "Recently viewed projects")
        assertContains(response, "My workspace")

    def test_query_count_does_not_grow_with_projects(
        self, logged_in_client, user, django_assert_num_queries
    ):
        ProjectFactory(owner=user)
        # session, user, projects, members prefetch, my memberships, due soon, my tasks,
        # sidebar projects
        with django_assert_num_queries(8):
            logged_in_client.get(reverse("projects:dashboard"))
        for _ in range(5):
            project = ProjectFactory(owner=user)
            TaskFactory(project=project, assignee=user, due_date=days(1))
            MembershipFactory(project=project)
        with django_assert_num_queries(8):
            logged_in_client.get(reverse("projects:dashboard"))


class TestStar:
    def url(self, project):
        return reverse("projects:toggle_star", args=[project.pk])

    def test_htmx_toggle_returns_button(self, logged_in_client, project, user, htmx):
        response = logged_in_client.post(self.url(project), **htmx)
        assertTemplateUsed(response, "projects/partials/star_button.html")
        assertContains(response, 'aria-pressed="true"')
        assert membership(project, user).is_starred

        response = logged_in_client.post(self.url(project), **htmx)
        assertContains(response, 'aria-pressed="false"')
        assert not membership(project, user).is_starred

    def test_stars_are_per_person(self, client, project, user, member, htmx):
        client.force_login(member)
        client.post(self.url(project), **htmx)
        assert membership(project, member).is_starred
        assert not membership(project, user).is_starred

    def test_plain_post_redirects(self, logged_in_client, project):
        response = logged_in_client.post(self.url(project))
        assert response.status_code == 302

    def test_non_member_gets_404(self, client, project, outsider):
        client.force_login(outsider)
        assert client.post(self.url(project)).status_code == 404

    def test_get_not_allowed(self, logged_in_client, project):
        assert logged_in_client.get(self.url(project)).status_code == 405


class TestRecentlyViewed:
    def test_full_board_load_records_the_visit(self, logged_in_client, project, user):
        logged_in_client.get(project.get_absolute_url())
        assert membership(project, user).last_viewed_at is not None

    def test_htmx_refresh_does_not(self, logged_in_client, project, user, htmx):
        logged_in_client.get(project.get_absolute_url(), **htmx)
        assert membership(project, user).last_viewed_at is None

    def test_sidebar_orders_by_last_viewed(self, user):
        older, newer, never = (ProjectFactory(owner=user) for _ in range(3))
        project_services.record_view(membership(older, user))
        project_services.record_view(membership(newer, user))
        assert [m.project for m in sidebar_memberships(user)][:2] == [newer, older]
        assert sidebar_memberships(user)[2].project == never


class TestSearch:
    @pytest.fixture
    def data(self, user):
        mine = ProjectFactory(owner=user, name="Apollo launch")
        TaskFactory(project=mine, title="Fix login")
        other = ProjectFactory(name="Apollo secret")
        TaskFactory(project=other, title="Fix secret login")
        return mine

    def test_dropdown_finds_projects_and_tasks_i_can_see(self, logged_in_client, data, htmx):
        response = logged_in_client.get(reverse("search"), {"q": "apollo"}, **htmx)
        assertTemplateUsed(response, "projects/partials/search_results.html")
        assertContains(response, "Apollo launch")
        assertNotContains(response, "Apollo secret")

        response = logged_in_client.get(reverse("search"), {"q": "login"}, **htmx)
        assertContains(response, "Fix login")
        assertNotContains(response, "Fix secret login")

    def test_full_page(self, logged_in_client, data):
        response = logged_in_client.get(reverse("search"), {"q": "login"})
        assertTemplateUsed(response, "projects/search.html")
        assertContains(response, "Fix login")

    def test_empty_query_returns_nothing(self, logged_in_client, data, htmx):
        response = logged_in_client.get(reverse("search"), {"q": "  "}, **htmx)
        assert response.content.strip() == b""

    def test_no_matches_message(self, logged_in_client, data, htmx):
        response = logged_in_client.get(reverse("search"), {"q": "zzz"}, **htmx)
        assertContains(response, "No projects or tasks match")

    def test_requires_login(self, client):
        assert client.get(reverse("search"), {"q": "x"}).status_code == 302


class TestMyTasks:
    @pytest.fixture
    def data(self, project, user, member):
        TaskFactory(project=project, title="Mine soon", assignee=user, due_date=days(2))
        TaskFactory(project=project, title="Mine later", assignee=user, due_date=days(20))
        TaskFactory(project=project, title="Mine done", assignee=user, status=Task.Status.DONE)
        TaskFactory(project=project, title="Theirs soon", assignee=member, due_date=days(3))
        TaskFactory(title="Elsewhere", assignee=user, due_date=days(1))  # not my project

    def titles(self, response):
        return [t.title for t in response.context["tasks"]]

    def test_open_tasks_assigned_to_me(self, logged_in_client, data):
        response = logged_in_client.get(reverse("my_tasks"))
        assert self.titles(response) == ["Mine soon", "Mine later"]

    def test_due_this_week(self, logged_in_client, data):
        assert self.titles(logged_in_client.get(reverse("my_tasks"), {"due": "week"})) == [
            "Mine soon"
        ]

    def test_everyone_due_this_week(self, logged_in_client, data):
        response = logged_in_client.get(reverse("my_tasks"), {"due": "week", "everyone": "1"})
        assert self.titles(response) == ["Mine soon", "Theirs soon"]

    def test_empty_state(self, logged_in_client):
        assertContains(logged_in_client.get(reverse("my_tasks")), "Nothing to do here")


class TestNotifications:
    @pytest.fixture
    def events(self, project, user, member):
        task = TaskFactory(project=project, title="Plan")
        task_services.add_comment(task, author=member, body="hi")  # someone else: counts
        task_services.add_comment(task, author=user, body="me")  # me: never notifies
        other = TaskFactory(title="Elsewhere")
        task_services.add_comment(other, author=other.project.owner, body="x")  # not my project
        return task

    def test_unread_count_ignores_my_own_actions_and_other_projects(self, user, events):
        assert activity_services.unread_count(user) == 1

    def test_badge(self, logged_in_client, events):
        response = logged_in_client.get(reverse("notifications:badge"))
        assertContains(response, "01")
        assertContains(response, 'id="notification-badge"')

    def test_opening_the_panel_marks_everything_read(self, logged_in_client, user, events):
        response = logged_in_client.get(reverse("notifications:panel"))
        assertContains(response, "commented on")
        assertContains(response, 'hx-swap-oob="true"')
        user.refresh_from_db()
        assert user.notifications_seen_at is not None
        assert activity_services.unread_count(user) == 0

    def test_new_activity_after_reading_is_unread_again(self, user, member, events):
        activity_services.mark_notifications_seen(user)
        task_services.add_comment(events, author=member, body="again")
        assert activity_services.unread_count(user) == 1

    def test_empty_panel(self, logged_in_client):
        assertContains(logged_in_client.get(reverse("notifications:panel")), "all caught up")

    def test_requires_login(self, client):
        assert client.get(reverse("notifications:badge")).status_code == 302
        assert client.get(reverse("notifications:panel")).status_code == 302


class TestShell:
    def test_signed_in_pages_have_sidebar_topbar_and_search(self, logged_in_client, project):
        response = logged_in_client.get(project.get_absolute_url())
        assertContains(response, 'aria-label="Main navigation"')
        assertContains(response, 'id="global-search"')
        assertContains(response, reverse("notifications:badge"))
        assertContains(response, project.name)

    def test_signed_out_pages_keep_the_simple_navbar(self, client):
        response = client.get(reverse("home"))
        assertNotContains(response, 'id="global-search"')
        assertContains(response, "Sign up")

    @pytest.mark.parametrize(
        "path,params,expected",
        [
            ("projects:dashboard", {}, "dashboard"),
            ("projects:dashboard", {"view": "starred"}, "starred"),
            ("my_tasks", {}, "my_tasks"),
            ("my_tasks", {"due": "week"}, "due_week"),
        ],
    )
    def test_nav_active(self, logged_in_client, path, params, expected):
        response = logged_in_client.get(reverse(path), params)
        assert response.context["nav_active"] == expected

    def test_nav_active_without_a_resolved_url(self, user):
        request = RequestFactory().get("/")
        request.user = user
        request.resolver_match = None
        assert nav_active(request) == ""

    def test_workspace_is_empty_for_anonymous_users(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        assert workspace(request) == {}
