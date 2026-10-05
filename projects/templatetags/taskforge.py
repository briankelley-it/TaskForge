"""Small template helpers shared across TaskForge templates. Load with {% load taskforge %}."""

import datetime

from django import template
from django.utils import timezone
from django.utils.timesince import timesince

register = template.Library()


@register.filter
def ago(value: datetime.datetime | None) -> str:
    """'just now' for the last minute, otherwise e.g. '3 hours ago'.

    Django's timesince says "0 minutes" for anything under a minute, which reads oddly
    right after you post a comment.
    """
    if not value:
        return ""
    if timezone.now() - value < datetime.timedelta(minutes=1):
        return "just now"
    # depth=1 keeps it short: "2 days" rather than "2 days, 3 hours".
    return f"{timesince(value, depth=1)} ago"
