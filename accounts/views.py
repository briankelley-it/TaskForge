from django.contrib import messages
from django.contrib.auth import login
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .demo import demo_user


@require_POST
def demo_login(request: HttpRequest) -> HttpResponse:
    """One click: sign in as the demo account and go to its dashboard."""
    user = demo_user()
    if user is None:
        raise Http404("The demo account isn't available.")
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(request, "You're exploring the TaskForge demo. Changes you make are shared.")
    return redirect("projects:dashboard")
