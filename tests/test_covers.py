"""Project cover images: placeholder, upload through the modal or the project form,
validation, replacing and removing, and who is allowed to change them."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from pytest_django.asserts import assertContains, assertTemplateUsed

from projects import services
from projects.models import COVER_PLACEHOLDER_URL, Project
from tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Uploads go to a throwaway folder, never the real media directory."""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def png(name: str = "cover.png", size=(60, 40)) -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", size, "#6366f1").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def url(project):
    return reverse("projects:cover", args=[project.pk])


def test_placeholder_until_a_cover_is_uploaded(logged_in_client, project):
    assert project.cover_url == COVER_PLACEHOLDER_URL == "https://placehold.co/600x400"
    assertContains(logged_in_client.get(reverse("projects:dashboard")), COVER_PLACEHOLDER_URL)


class TestCoverModal:
    def test_htmx_get_shows_dropzone(self, logged_in_client, project, htmx):
        response = logged_in_client.get(url(project), **htmx)
        assertTemplateUsed(response, "projects/partials/cover_form.html")
        assertContains(response, 'type="file"')
        assertContains(response, 'accept="image/*"')
        assertContains(response, 'hx-encoding="multipart/form-data"')

    def test_upload(self, logged_in_client, project, htmx, media_root):
        response = logged_in_client.post(url(project), {"cover": png()}, **htmx)

        assert response.status_code == 204
        assert response["HX-Refresh"] == "true"
        project.refresh_from_db()
        assert project.cover.name.startswith("covers/")
        assert project.cover.name.endswith(".png")
        assert (media_root / project.cover.name).exists()
        assert project.cover_url.startswith("/media/covers/")
        assertContains(logged_in_client.get(reverse("projects:dashboard")), project.cover.url)

    def test_replacing_deletes_the_old_file(self, logged_in_client, project, htmx, media_root):
        logged_in_client.post(url(project), {"cover": png("one.png")}, **htmx)
        project.refresh_from_db()
        first = media_root / project.cover.name

        logged_in_client.post(url(project), {"cover": png("two.png")}, **htmx)
        project.refresh_from_db()
        assert not first.exists()
        assert (media_root / project.cover.name).exists()

    def test_remove_goes_back_to_placeholder(self, logged_in_client, project, htmx, media_root):
        logged_in_client.post(url(project), {"cover": png()}, **htmx)
        project.refresh_from_db()
        stored = media_root / project.cover.name

        response = logged_in_client.post(url(project), {"remove": "1"}, **htmx)
        assert response.status_code == 204
        project.refresh_from_db()
        assert not project.cover
        assert not stored.exists()
        assert project.cover_url == COVER_PLACEHOLDER_URL

    def test_submitting_without_a_file_shows_error(self, logged_in_client, project, htmx):
        response = logged_in_client.post(url(project), {}, **htmx)
        assert response.status_code == 200
        assertContains(response, "Choose an image to upload")

    def test_rejects_files_that_are_not_images(self, logged_in_client, project, htmx):
        fake = SimpleUploadedFile("evil.png", b"not really a png", content_type="image/png")
        response = logged_in_client.post(url(project), {"cover": fake}, **htmx)
        assert response.status_code == 200
        assert response.context["form"].errors["cover"]
        project.refresh_from_db()
        assert not project.cover

    def test_rejects_other_file_types(self, logged_in_client, project, htmx):
        buffer = io.BytesIO()
        Image.new("RGB", (10, 10)).save(buffer, format="BMP")
        bmp = SimpleUploadedFile("cover.bmp", buffer.getvalue(), content_type="image/bmp")
        response = logged_in_client.post(url(project), {"cover": bmp}, **htmx)
        assert response.context["form"].errors["cover"]

    def test_rejects_files_over_5_mb(self, logged_in_client, project, htmx, monkeypatch):
        monkeypatch.setattr("projects.models.COVER_MAX_MB", 0)
        response = logged_in_client.post(url(project), {"cover": png()}, **htmx)
        assertContains(response, "up to 0 MB")

    def test_plain_post_redirects_to_safe_next_only(self, logged_in_client, project):
        board = project.get_absolute_url()
        response = logged_in_client.post(url(project), {"cover": png(), "next": board})
        assert response.url == board
        response = logged_in_client.post(
            url(project), {"cover": png(), "next": "https://evil.example.com/"}
        )
        assert response.url == reverse("projects:dashboard")

    def test_plain_get_renders_full_page(self, logged_in_client, project):
        assertTemplateUsed(logged_in_client.get(url(project)), "projects/cover_page.html")


class TestCoverPermissions:
    def test_logged_out_redirects(self, client, project):
        assert client.get(url(project)).status_code == 302

    def test_non_member_gets_404(self, client, project, outsider):
        client.force_login(outsider)
        assert client.post(url(project), {"cover": png()}).status_code == 404

    def test_member_who_is_not_owner_gets_403(self, client, project, member):
        client.force_login(member)
        assert client.post(url(project), {"cover": png()}).status_code == 403
        project.refresh_from_db()
        assert not project.cover

    def test_cover_button_only_shown_to_owner(self, client, project, member):
        client.force_login(member)
        response = client.get(reverse("projects:dashboard"))
        assert url(project) not in response.content.decode()


class TestProjectFormCover:
    def test_create_with_cover(self, logged_in_client, media_root):
        response = logged_in_client.post(
            reverse("projects:create"), {"name": "Launch", "description": "", "cover": png()}
        )
        project = Project.objects.get(name="Launch")
        assert response.status_code == 302
        assert (media_root / project.cover.name).exists()

    def test_create_without_cover_uses_placeholder(self, logged_in_client):
        logged_in_client.post(reverse("projects:create"), {"name": "Plain", "description": ""})
        assert Project.objects.get(name="Plain").cover_url == COVER_PLACEHOLDER_URL

    def test_edit_replaces_cover_and_deletes_old_file(self, logged_in_client, project, media_root):
        services.set_cover(project, png("old.png"))
        old = media_root / project.cover.name

        logged_in_client.post(
            reverse("projects:update", args=[project.pk]),
            {"name": project.name, "description": "", "cover": png("new.png")},
        )
        project.refresh_from_db()
        assert not old.exists()
        assert (media_root / project.cover.name).exists()

    def test_edit_without_new_file_keeps_cover(self, logged_in_client, project, media_root):
        services.set_cover(project, png())
        name = project.cover.name
        logged_in_client.post(
            reverse("projects:update", args=[project.pk]), {"name": "Renamed", "description": ""}
        )
        project.refresh_from_db()
        assert project.cover.name == name
        assert (media_root / name).exists()

    def test_form_uses_multipart_and_dropzone(self, logged_in_client):
        response = logged_in_client.get(reverse("projects:create"))
        assertContains(response, 'enctype="multipart/form-data"')
        assertContains(response, "data-dropzone")


def test_remove_cover_without_one_is_harmless():
    project = ProjectFactory()
    services.remove_cover(project)
    assert not project.cover
