from allauth.account.forms import SignupForm as AllauthSignupForm
from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import User


class AdminUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "display_name")


class AdminUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ("email", "display_name", "first_name", "last_name")


class SignupForm(AllauthSignupForm):
    """allauth's sign-up form plus a display name."""

    display_name = forms.CharField(
        label="Full name",
        max_length=80,
        widget=forms.TextInput(attrs={"autocomplete": "name", "placeholder": "Ada Lovelace"}),
    )

    field_order = ["display_name", "email", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "password2" in self.fields:
            self.fields["password2"].label = "Confirm password"

    def save(self, request):
        user = super().save(request)
        user.display_name = self.cleaned_data["display_name"].strip()
        user.save(update_fields=["display_name"])
        return user
