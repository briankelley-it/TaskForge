"""The public demo login on the auth pages, and messages shown as toasts."""

import pytest
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def demo(settings):
    return UserFactory(email=settings.DEMO_EMAIL, display_name="Demo User")


class TestDemoPanel:
    @pytest.mark.parametrize("page", ["account_signup", "account_login"])
    def test_shows_demo_details_and_one_click_button(self, client, demo, settings, page):
        response = client.get(reverse(page))
        assertContains(response, "Just want to look around?")
        assertContains(response, settings.DEMO_EMAIL)
        assertContains(response, settings.DEMO_PASSWORD)
        assertContains(response, reverse("demo_login"))
        assertContains(response, "data-demo-fill")

    def test_hidden_until_the_demo_account_is_seeded(self, client):
        assertNotContains(client.get(reverse("account_signup")), "Just want to look around?")

    def test_hidden_when_switched_off(self, client, demo, settings):
        settings.DEMO_LOGIN_ENABLED = False
        assertNotContains(client.get(reverse("account_signup")), "Just want to look around?")


class TestDemoLogin:
    def test_logs_in_as_demo_and_goes_to_dashboard(self, client, demo):
        response = client.post(reverse("demo_login"))
        assert response.status_code == 302
        assert response.url == reverse("projects:dashboard")
        assert client.session["_auth_user_id"] == str(demo.pk)

    def test_404_without_demo_account(self, client):
        assert client.post(reverse("demo_login")).status_code == 404

    def test_404_when_switched_off(self, client, demo, settings):
        settings.DEMO_LOGIN_ENABLED = False
        assert client.post(reverse("demo_login")).status_code == 404

    def test_inactive_demo_account_cannot_be_used(self, client, demo):
        demo.is_active = False
        demo.save()
        assert client.post(reverse("demo_login")).status_code == 404

    def test_get_not_allowed(self, client, demo):
        assert client.get(reverse("demo_login")).status_code == 405

    def test_password_on_the_page_really_works(self, client, demo, settings):
        demo.set_password(settings.DEMO_PASSWORD)
        demo.save()
        response = client.post(
            reverse("account_login"),
            {"login": settings.DEMO_EMAIL, "password": settings.DEMO_PASSWORD},
        )
        assert response.status_code == 302
        assert client.session["_auth_user_id"] == str(demo.pk)


def test_messages_render_as_auto_dismissing_toasts(client, demo):
    response = client.post(reverse("demo_login"), follow=True)
    assertContains(response, 'id="toasts"')
    assertContains(response, "data-toast")
    assertContains(response, "exploring the TaskForge demo")


def test_missing_demo_settings_hide_the_panel_instead_of_crashing(client, demo, settings):
    del settings.DEMO_LOGIN_ENABLED
    response = client.get(reverse("account_signup"))
    assert response.status_code == 200
    assertNotContains(response, "Just want to look around?")
    assert client.post(reverse("demo_login")).status_code == 404
