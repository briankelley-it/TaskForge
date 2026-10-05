"""python manage.py seed_demo

Creates a demo account with two projects and about 20 tasks, so a fresh install or the
live demo never looks empty. It goes through the real services, so the activity feed is
filled in too. Running it again deletes the old demo data and starts over.
"""

import datetime
import random

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from projects import services as project_services
from projects.models import Project
from tasks import services as task_services
from tasks.models import Task

User = get_user_model()

# The login and sign-up pages advertise these, so they come from settings.
DEMO_EMAIL = settings.DEMO_EMAIL
DEFAULT_PASSWORD = settings.DEMO_PASSWORD
TEAMMATES = [
    ("sam@taskforge.dev", "Sam Rivera"),
    ("priya@taskforge.dev", "Priya Natarajan"),
]

S, P = Task.Status, Task.Priority
# (title, status, priority, due in N days or None, assignee index: 0 = demo user)
PROJECTS = {
    (
        "Website relaunch",
        "New marketing site for the spring launch: design, copy and hosting.",
    ): [
        ("Design the homepage hero", S.DONE, P.HIGH, -6, 0),
        ("Write pricing page copy", S.DONE, P.MEDIUM, -3, 1),
        ("Choose a font pairing", S.DONE, P.LOW, None, 2),
        ("Build the contact form", S.IN_PROGRESS, P.HIGH, 1, 0),
        ("Set up hosting and SSL", S.IN_PROGRESS, P.HIGH, -1, 1),
        ("Compress hero images", S.IN_PROGRESS, P.MEDIUM, 4, 2),
        ("Write the About page", S.TODO, P.MEDIUM, 6, 1),
        ("Add analytics", S.TODO, P.LOW, 10, None),
        ("Accessibility audit", S.TODO, P.HIGH, 2, 0),
        ("Set up 301 redirects from the old site", S.TODO, P.MEDIUM, -2, 2),
        ("Launch announcement email", S.TODO, P.LOW, 14, None),
    ],
    (
        "Mobile app beta",
        "Get the iOS and Android beta into testers' hands.",
    ): [
        ("Sign-in with email", S.DONE, P.HIGH, -10, 0),
        ("Push notification permissions", S.DONE, P.MEDIUM, -4, 2),
        ("Offline mode for task lists", S.IN_PROGRESS, P.HIGH, 3, 0),
        ("Crash reporting", S.IN_PROGRESS, P.MEDIUM, 0, 1),
        ("App Store screenshots", S.TODO, P.MEDIUM, 7, 2),
        ("Beta tester onboarding doc", S.TODO, P.LOW, 9, 1),
        ("Fix keyboard covering the input", S.TODO, P.HIGH, -1, 0),
        ("Dark mode icons", S.TODO, P.LOW, None, None),
    ],
}
COMMENTS = [
    "I'll take a first pass at this today.",
    "Blocked until we get the final copy, can someone check?",
    "Looks good to me 👍",
    "Pushed a fix, can you double-check on your phone?",
    "Moved this up, it's blocking the launch.",
]


class Command(BaseCommand):
    help = "Create (or reset) a demo user with two projects and sample tasks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=f"Password for {DEMO_EMAIL} (default: {DEFAULT_PASSWORD})",
        )

    @transaction.atomic
    def handle(self, *args, password: str, **options):
        rng = random.Random(42)  # same demo every time
        today = timezone.localdate()

        demo = self._user(DEMO_EMAIL, "Demo User", password)
        team = [demo] + [self._user(email, name, password) for email, name in TEAMMATES]

        # Start over: remove projects the demo user owns (tasks, comments and
        # activity go with them through cascades).
        Project.objects.filter(owner=demo).delete()

        task_count = 0
        for index, ((name, description), tasks) in enumerate(PROJECTS.items()):
            project = project_services.create_project(
                owner=demo, name=name, description=description
            )
            if index == 0:
                # Star one project so the dashboard shows off the feature.
                project_services.toggle_star(project.memberships.get(user=demo))
            for member in team[1:]:
                project_services.invite_member(project=project, email=member.email)

            for title, status, priority, due_in, assignee_index in tasks:
                actor = rng.choice(team)
                task = task_services.create_task(
                    project=project,
                    created_by=actor,
                    title=title,
                    priority=priority,
                    due_date=today + datetime.timedelta(days=due_in)
                    if due_in is not None
                    else None,
                    assignee=team[assignee_index] if assignee_index is not None else None,
                )
                # Move it like a person would, so the feed shows "moved" entries.
                if status != S.TODO:
                    task_services.move_task(task, status=S.IN_PROGRESS, position=0, actor=actor)
                if status == S.DONE:
                    task_services.move_task(task, status=S.DONE, position=0, actor=actor)
                if rng.random() < 0.4:
                    task_services.add_comment(
                        task, author=rng.choice(team), body=rng.choice(COMMENTS)
                    )
                task_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo ready: {len(PROJECTS)} projects, {task_count} tasks.\n"
                f"Log in as {DEMO_EMAIL} / {password}"
            )
        )

    def _user(self, email: str, name: str, password: str):
        user, _ = User.objects.get_or_create(email=email, defaults={"display_name": name})
        user.display_name = name
        user.set_password(password)
        user.save()
        return user
