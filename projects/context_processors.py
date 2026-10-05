"""Data every signed-in page's shell needs: the sidebar's recent projects and which
navigation item is active."""

from django.utils.functional import SimpleLazyObject

from .dashboard import sidebar_memberships


def nav_active(request) -> str:
    match = request.resolver_match
    view = match.view_name if match else ""
    if view == "my_tasks":
        return "due_week" if request.GET.get("due") == "week" else "my_tasks"
    if view == "projects:dashboard":
        return "starred" if request.GET.get("view") == "starred" else "dashboard"
    return ""


def workspace(request) -> dict:
    if not request.user.is_authenticated:
        return {}
    return {
        # Lazy: the query only runs if a template actually draws the sidebar.
        "sidebar_memberships": SimpleLazyObject(lambda: sidebar_memberships(request.user)),
        "nav_active": nav_active(request),
    }
