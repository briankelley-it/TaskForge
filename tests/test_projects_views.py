import pytest
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains, assertRedirects

from projects.models import Membership, Project
from tests.factories import MembershipFactory, ProjectFactory, UserFactory

pytestmark = pytest.mark.django_db

HTMX = {"HTTP_HX_REQUEST": "true"}


class TestDashboard:
    def test_lists_only_my_projects_with_member_counts(self, logged_in_client, user):
        mine = ProjectFactory(owner=user, name="Mine")
        MembershipFactory(project=mine)
        joined = MembershipFactory(user=user, project=ProjectFactory(name="Joined")).project
        ProjectFactory(name="Not mine")

        response = logged_in_client.get(reverse("projects:dashboard"))

        assert set(response.context["projects"]) == {mine, joined}
        counts = {p.name: p.member_count for p in response.context["projects"]}
        assert counts == {"Mine": 2, "Joined": 2}
        assertNotContains(response, "Not mine")

    def test_empty_state(self, logged_in_client):
        response = logged_in_client.get(reverse("projects:dashboard"))
        assertContains(response, "No projects yet")


class TestCreateProject:
    def test_form_renders(self, logged_in_client):
        assert logged_in_client.get(reverse("projects:create")).status_code == 200

    def test_creates_project_owned_by_me(self, logged_in_client, user):
        response = logged_in_client.post(
            reverse("projects:create"), {"name": "Apollo", "description": "Moon"}
        )
        project = Project.objects.get(name="Apollo")
        assertRedirects(response, project.get_absolute_url())
        assert project.owner == user
        assert project.memberships.get(user=user).role == Membership.Role.OWNER

    def test_name_is_required(self, logged_in_client):
        response = logged_in_client.post(reverse("projects:create"), {"name": ""})
        assert response.status_code == 200
        assert response.context["form"].errors["name"]
        assert not Project.objects.exists()


class TestMembersPage:
    def test_owner_sees_edit_controls_and_invite_form(self, logged_in_client, project):
        response = logged_in_client.get(reverse("projects:members", args=[project.pk]))
        assertContains(response, project.name)
        assertContains(response, reverse("projects:update", args=[project.pk]))
        assertContains(response, reverse("projects:invite_member", args=[project.pk]))

    def test_member_sees_project_without_owner_controls(self, client, project, member):
        client.force_login(member)
        response = client.get(reverse("projects:members", args=[project.pk]))
        assert response.status_code == 200
        assertNotContains(response, reverse("projects:update", args=[project.pk]))
        assertNotContains(response, reverse("projects:invite_member", args=[project.pk]))


class TestUpdateAndDelete:
    def test_owner_can_edit(self, logged_in_client, project):
        url = reverse("projects:update", args=[project.pk])
        assert logged_in_client.get(url).status_code == 200
        response = logged_in_client.post(url, {"name": "Renamed", "description": ""})
        assertRedirects(response, project.get_absolute_url())
        project.refresh_from_db()
        assert project.name == "Renamed"

    def test_owner_can_delete(self, logged_in_client, project):
        url = reverse("projects:delete", args=[project.pk])
        assert logged_in_client.get(url).status_code == 200
        response = logged_in_client.post(url)
        assertRedirects(response, reverse("projects:dashboard"))
        assert not Project.objects.filter(pk=project.pk).exists()


class TestInviteMember:
    def url(self, project):
        return reverse("projects:invite_member", args=[project.pk])

    def test_htmx_invite_adds_member_and_returns_partial(self, logged_in_client, project):
        invitee = UserFactory(email="grace@example.com")
        response = logged_in_client.post(self.url(project), {"email": invitee.email}, **HTMX)

        assert response.status_code == 200
        assert [t.name for t in response.templates][0] == "projects/partials/members.html"
        assertContains(response, f"Added {invitee}")
        assert project.memberships.filter(user=invitee).exists()

    def test_unknown_email_shows_clear_message(self, logged_in_client, project):
        response = logged_in_client.post(self.url(project), {"email": "nobody@example.com"}, **HTMX)
        assertContains(response, "No TaskForge account uses nobody@example.com")
        assert project.memberships.count() == 1

    def test_already_member_message(self, logged_in_client, project, member):
        response = logged_in_client.post(self.url(project), {"email": member.email}, **HTMX)
        assertContains(response, "already a member")

    def test_invalid_email_shows_form_error(self, logged_in_client, project):
        response = logged_in_client.post(self.url(project), {"email": "not-an-email"}, **HTMX)
        assertContains(response, "Enter a valid email address")

    def test_plain_post_redirects_with_message(self, logged_in_client, project):
        UserFactory(email="grace@example.com")
        response = logged_in_client.post(
            self.url(project), {"email": "grace@example.com"}, follow=True
        )
        assertRedirects(response, reverse("projects:members", args=[project.pk]))
        assertContains(response, "Added")

    def test_get_not_allowed(self, logged_in_client, project):
        assert logged_in_client.get(self.url(project)).status_code == 405


class TestRemoveMember:
    def url(self, project, user):
        return reverse("projects:remove_member", args=[project.pk, user.pk])

    def test_owner_removes_member(self, logged_in_client, project, member):
        response = logged_in_client.post(self.url(project, member), **HTMX)
        assertContains(response, "Removed")
        assert not project.memberships.filter(user=member).exists()

    def test_owner_cannot_remove_themself(self, logged_in_client, project, user):
        response = logged_in_client.post(self.url(project, user), **HTMX)
        assertContains(response, "can&#x27;t be removed")
        assert project.memberships.filter(user=user).exists()

    def test_removing_a_non_member_is_404(self, logged_in_client, project):
        stranger = UserFactory()
        assert logged_in_client.post(self.url(project, stranger), **HTMX).status_code == 404


def test_admin_pages_render(admin_client, project):
    for url in [
        reverse("admin:projects_project_changelist"),
        reverse("admin:projects_project_change", args=[project.pk]),
        reverse("admin:projects_membership_changelist"),
    ]:
        assert admin_client.get(url).status_code == 200
