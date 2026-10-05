"""Small template helpers shared across TaskForge templates. Load with {% load taskforge %}."""

import datetime

from django import template
from django.utils import timezone
from django.utils.timesince import timesince

register = template.Library()

# Avatar colours, as gradient classes. Kept here (not built from strings) so Tailwind's
# scanner sees every class; assets/tailwind.css lists this folder as a source.
AVATAR_COLOURS = [
    "bg-gradient-to-br from-violet-500 to-purple-600",
    "bg-gradient-to-br from-amber-400 to-orange-500",
    "bg-gradient-to-br from-pink-500 to-rose-500",
    "bg-gradient-to-br from-emerald-400 to-green-600",
    "bg-gradient-to-br from-sky-400 to-blue-600",
    "bg-gradient-to-br from-fuchsia-500 to-pink-600",
]
SIZES = {
    "xs": "h-6 w-6 text-[9px]",
    "sm": "h-8 w-8 text-[11px]",
    "md": "h-9 w-9 text-xs",
    "lg": "h-11 w-11 text-sm",
}


def colour_for(key: int | None) -> str:
    return AVATAR_COLOURS[(key or 0) % len(AVATAR_COLOURS)]


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


@register.inclusion_tag("components/avatar.html")
def avatar(user, size: str = "sm", badge: int | None = None) -> dict:
    """A round, coloured avatar with the user's initials and an optional count badge."""
    return {
        "label": user.initials if user else "?",
        "title": user.name if user else "Deleted user",
        "colour": colour_for(user.pk if user else None),
        "size": SIZES[size],
        "badge": badge,
    }


@register.inclusion_tag("components/avatar_stack.html")
def avatar_stack(users, limit: int = 3, size: str = "sm") -> dict:
    """Up to `limit` overlapping avatars; the rest are summarised as "+02"."""
    users = list(users)
    return {"shown": users[:limit], "extra": max(len(users) - limit, 0), "size": size}


@register.inclusion_tag("components/project_avatar.html")
def project_avatar(project, size: str = "md") -> dict:
    """A project's first letter in its own colour, for the sidebar."""
    return {
        "project": project,
        "label": project.name[:1].upper(),
        "colour": colour_for(project.pk),
        "size": SIZES[size],
    }
