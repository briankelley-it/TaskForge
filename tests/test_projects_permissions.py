"""Who can reach which project URL.

Every project URL is listed once in PROJECT_URLS, so a new URL only needs adding
here to be covered by the logged-out, non-member and non-owner checks.
"""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.urls import reverse

from projects.models import Project
from projects.permissions import get_membership

pytestmark = pytest.mark.django_db

# (url name, HTTP method, owner_only)
PROJECT_URLS = [
    ("projects:members", "get", False),
    ("projects:update", "get", True),
    ("projects:update", "post", True),
    ("projects:delete", "get", True),
    ("projects:delete", "post", True),
    ("projects:invite_member", "post", True),
    ("projects:remove_member", "post", True),
]


def build_url(name, project, member):
    if name == "projects:remove_member":
        return reverse(name, args=[project.pk, member.pk])
    return reverse(name, args=[project.pk])


@pytest.mark.parametrize("name,method,_owner_only", PROJECT_URLS)
def test_logged_out_user_is_redirected_to_login(client, project, member, name, method, _owner_only):
    url = build_url(name, project, member)
    response = getattr(client, method)(url)
    assert response.status_code == 302
    assert response.url.startswith(reverse("account_login"))


@pytest.mark.parametrize("name,method,_owner_only", PROJECT_URLS)
def test_non_member_gets_404(client, project, member, outsider, name, method, _owner_only):
    client.force_login(outsider)
    response = getattr(client, method)(build_url(name, project, member))
    assert response.status_code == 404


@pytest.mark.parametrize("name,method", [(n, m) for n, m, owner_only in PROJECT_URLS if owner_only])
def test_member_who_is_not_owner_gets_403_on_owner_actions(client, project, member, name, method):
    client.force_login(member)
    response = getattr(client, method)(build_url(name, project, member))
    assert response.status_code == 403


def test_member_cannot_edit_project(client, project, member):
    client.force_login(member)
    client.post(reverse("projects:update", args=[project.pk]), {"name": "Hijacked"})
    project.refresh_from_db()
    assert project.name != "Hijacked"


def test_member_cannot_delete_project(client, project, member):
    client.force_login(member)
    client.post(reverse("projects:delete", args=[project.pk]))
    assert Project.objects.filter(pk=project.pk).exists()


@pytest.mark.parametrize("name", ["projects:dashboard", "projects:create"])
def test_logged_out_user_is_redirected_from_dashboard_and_create(client, name):
    response = client.get(reverse(name))
    assert response.status_code == 302
    assert response.url.startswith(reverse("account_login"))


def test_nonexistent_project_is_404(logged_in_client):
    assert logged_in_client.get(reverse("projects:members", args=[99999])).status_code == 404


def test_get_membership_rejects_anonymous_user(project):
    with pytest.raises(Http404):
        get_membership(AnonymousUser(), project.pk)
