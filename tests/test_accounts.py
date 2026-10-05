import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

from tests.factories import DEFAULT_PASSWORD, UserFactory

User = get_user_model()

pytestmark = pytest.mark.django_db


class TestUserModel:
    def test_custom_user_model_is_active(self):
        assert User._meta.label == "accounts.User"

    def test_email_is_the_login_field_and_there_is_no_username(self):
        assert User.USERNAME_FIELD == "email"
        assert not hasattr(User, "username") or User.username is None

    def test_create_user_normalises_email(self):
        user = User.objects.create_user("Ada@EXAMPLE.com", "pw-12345!")
        assert user.email == "Ada@example.com"
        assert user.check_password("pw-12345!")
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_user_requires_email(self):
        with pytest.raises(ValueError, match="email"):
            User.objects.create_user("", "pw")

    def test_create_superuser(self):
        admin = User.objects.create_superuser("admin@example.com", "pw-12345!")
        assert admin.is_staff
        assert admin.is_superuser

    def test_create_superuser_rejects_is_staff_false(self):
        with pytest.raises(ValueError):
            User.objects.create_superuser("admin@example.com", "pw", is_staff=False)

    def test_email_is_unique(self):
        from django.db import IntegrityError

        UserFactory(email="same@example.com")
        with pytest.raises(IntegrityError):
            UserFactory(email="same@example.com")

    def test_str_prefers_display_name(self):
        assert str(UserFactory(display_name="Ada Lovelace")) == "Ada Lovelace"
        assert str(UserFactory(display_name="", email="grace@example.com")) == "grace@example.com"

    def test_name_falls_back_to_email_prefix(self):
        assert UserFactory(display_name="", email="grace@example.com").name == "grace"


class TestAuthPages:
    def test_home_page_renders_for_anonymous_user(self, client):
        response = client.get(reverse("home"))
        assert response.status_code == 200
        assert b"Sign up" in response.content

    def test_home_page_redirects_logged_in_user_to_dashboard(self, logged_in_client):
        response = logged_in_client.get(reverse("home"))
        assert response.status_code == 302
        assert response.url == reverse("projects:dashboard")

    @pytest.mark.parametrize(
        "url_name", ["account_login", "account_signup", "account_reset_password"]
    )
    def test_auth_pages_render(self, client, url_name):
        response = client.get(reverse(url_name))
        assert response.status_code == 200

    def test_base_template_sends_csrf_token_with_htmx_requests(self, client):
        response = client.get(reverse("home"))
        assert b"X-CSRFToken" in response.content

    def test_signup_creates_user_and_logs_in(self, client):
        response = client.post(
            reverse("account_signup"),
            {
                "email": "new@example.com",
                "password1": DEFAULT_PASSWORD,
                "password2": DEFAULT_PASSWORD,
            },
        )
        assert response.status_code == 302
        user = User.objects.get(email="new@example.com")
        assert client.session["_auth_user_id"] == str(user.pk)

    def test_login_with_email(self, client):
        UserFactory(email="ada@example.com")
        response = client.post(
            reverse("account_login"), {"login": "ada@example.com", "password": DEFAULT_PASSWORD}
        )
        assert response.status_code == 302
        assert response.url == reverse("projects:dashboard")

    def test_login_with_wrong_password_fails(self, client):
        UserFactory(email="ada@example.com")
        response = client.post(
            reverse("account_login"), {"login": "ada@example.com", "password": "wrong"}
        )
        assert response.status_code == 200
        assert "_auth_user_id" not in client.session

    def test_logout(self, logged_in_client):
        response = logged_in_client.post(reverse("account_logout"))
        assert response.status_code == 302
        assert "_auth_user_id" not in logged_in_client.session

    def test_password_reset_sends_email(self, client):
        UserFactory(email="ada@example.com")
        response = client.post(reverse("account_reset_password"), {"email": "ada@example.com"})
        assert response.status_code == 302
        assert len(mail.outbox) == 1
        assert "ada@example.com" in mail.outbox[0].to


class TestAdmin:
    def test_admin_user_pages_render(self, client):
        admin = User.objects.create_superuser("admin@example.com", "pw-12345!")
        client.force_login(admin)
        assert client.get(reverse("admin:accounts_user_changelist")).status_code == 200
        assert client.get(reverse("admin:accounts_user_add")).status_code == 200
        assert client.get(reverse("admin:accounts_user_change", args=[admin.pk])).status_code == 200
