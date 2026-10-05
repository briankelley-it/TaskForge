"""The split-screen login and sign-up pages."""

import pytest
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains, assertTemplateUsed

from accounts.models import User
from tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


class TestLoginPage:
    def test_design(self, client):
        response = client.get(reverse("account_login"))
        assertTemplateUsed(response, "account/login.html")
        assertTemplateUsed(response, "allauth/layouts/entrance.html")
        assertContains(response, "Welcome back to TaskForge")
        assertContains(response, "img/auth/login.jpg")
        assertContains(response, "float-field")
        assertContains(response, "Forgot password?")
        assertContains(response, 'name="remember"')
        assertContains(response, "data-password-toggle")
        assertContains(response, reverse("account_signup"))
        # Full-screen card: the public navbar (with its "Log in" button) is not shown.
        assertNotContains(response, ">Log in</a>")

    def test_wrong_password_shows_error_and_keeps_email(self, client):
        UserFactory(email="ada@example.com")
        response = client.post(
            reverse("account_login"), {"login": "ada@example.com", "password": "nope"}
        )
        assertContains(response, "not correct")
        assertContains(response, 'value="ada@example.com"')
        # The password is never echoed back into the page.
        assertNotContains(response, 'value="nope"')

    def test_remember_me_off_ends_session_at_browser_close(self, client):
        UserFactory(email="ada@example.com")
        client.post(
            reverse("account_login"), {"login": "ada@example.com", "password": DEFAULT_PASSWORD}
        )
        assert client.session.get_expire_at_browser_close()

    def test_remember_me_on_keeps_session(self, client):
        UserFactory(email="ada@example.com")
        client.post(
            reverse("account_login"),
            {"login": "ada@example.com", "password": DEFAULT_PASSWORD, "remember": "on"},
        )
        assert not client.session.get_expire_at_browser_close()


class TestSignupPage:
    def test_design(self, client):
        response = client.get(reverse("account_signup"))
        assertTemplateUsed(response, "account/signup.html")
        assertContains(response, "Create your TaskForge account")
        assertContains(response, "img/auth/signup.jpg")
        assertContains(response, "Full name")
        assertContains(response, "Confirm password")
        assertContains(response, "data-strength-for")

    def test_name_is_required(self, client):
        response = client.post(
            reverse("account_signup"),
            {
                "email": "x@example.com",
                "password1": DEFAULT_PASSWORD,
                "password2": DEFAULT_PASSWORD,
            },
        )
        assert response.status_code == 200
        assert response.context["form"].errors["display_name"]
        assert not User.objects.filter(email="x@example.com").exists()

    def test_mismatched_passwords_show_field_error(self, client):
        response = client.post(
            reverse("account_signup"),
            {
                "display_name": "Ada",
                "email": "x@example.com",
                "password1": DEFAULT_PASSWORD,
                "password2": "different-password-1",
            },
        )
        assertContains(response, "float-field-error")


class TestGoogleButton:
    def test_hidden_until_configured(self, client):
        assertNotContains(client.get(reverse("account_login")), "Continue with Google")

    def test_shown_when_keys_are_set(self, client, settings):
        settings.GOOGLE_CLIENT_ID = "id"
        settings.GOOGLE_CLIENT_SECRET = "secret"
        settings.SOCIALACCOUNT_PROVIDERS = {
            "google": {"APPS": [{"client_id": "id", "secret": "secret"}]}
        }
        response = client.get(reverse("account_signup"))
        assertContains(response, "Continue with Google")
        assertContains(response, "/accounts/google/login/")


def test_other_account_pages_use_the_same_layout(client):
    response = client.get(reverse("account_reset_password"))
    assertTemplateUsed(response, "allauth/layouts/entrance.html")
    assertContains(response, "img/auth/login.jpg")
