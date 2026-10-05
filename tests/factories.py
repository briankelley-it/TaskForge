import factory

from accounts.models import User
from projects.models import Membership, Project
from tasks.models import Comment, Task

DEFAULT_PASSWORD = "correct-horse-battery-staple"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    display_name = factory.Faker("name")
    # Hashed before saving, so factories can log in with DEFAULT_PASSWORD.
    password = factory.django.Password(DEFAULT_PASSWORD)


class ProjectFactory(factory.django.DjangoModelFactory):
    """A project plus its owner's membership, matching services.create_project."""

    class Meta:
        model = Project
        skip_postgeneration_save = True

    name = factory.Sequence(lambda n: f"Project {n}")
    description = factory.Faker("sentence")
    owner = factory.SubFactory(UserFactory)
    owner_membership = factory.RelatedFactory(
        "tests.factories.MembershipFactory",
        factory_related_name="project",
        user=factory.SelfAttribute("..owner"),
        role=Membership.Role.OWNER,
    )


class MembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Membership

    project = factory.SubFactory(ProjectFactory)
    user = factory.SubFactory(UserFactory)
    role = Membership.Role.MEMBER


class TaskFactory(factory.django.DjangoModelFactory):
    """A task at the bottom of its column, like services.create_task makes."""

    class Meta:
        model = Task

    project = factory.SubFactory(ProjectFactory)
    title = factory.Sequence(lambda n: f"Task {n}")
    status = Task.Status.TODO
    priority = Task.Priority.MEDIUM
    created_by = factory.SelfAttribute("project.owner")

    @factory.lazy_attribute
    def position(self):
        return Task.objects.filter(project=self.project, status=self.status).count()


class CommentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Comment

    task = factory.SubFactory(TaskFactory)
    author = factory.SelfAttribute("task.project.owner")
    body = factory.Faker("sentence")
