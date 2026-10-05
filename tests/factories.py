import factory

from accounts.models import User

DEFAULT_PASSWORD = "correct-horse-battery-staple"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    display_name = factory.Faker("name")
    # Hashed before saving, so factories can log in with DEFAULT_PASSWORD.
    password = factory.django.Password(DEFAULT_PASSWORD)
