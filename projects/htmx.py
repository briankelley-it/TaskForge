from django.http import HttpRequest


def is_htmx(request: HttpRequest) -> bool:
    """HTMX marks its requests with this header. Used to choose a partial or a full page."""
    return request.headers.get("HX-Request") == "true"
