from django import forms

from .models import Project


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description", "cover"]
        labels = {"cover": "Cover image"}
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Website relaunch", "autofocus": True}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "cover": forms.FileInput(
                attrs={"accept": "image/*", "data-cover-input": True, "class": "sr-only"}
            ),
        }


class CoverForm(forms.ModelForm):
    """Just the cover image, for the quick "Change cover" modal."""

    class Meta:
        model = Project
        fields = ["cover"]
        widgets = {
            "cover": forms.FileInput(
                attrs={"accept": "image/*", "data-cover-input": True, "class": "sr-only"}
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cover"].required = True
        self.fields["cover"].error_messages["required"] = "Choose an image to upload."


class InviteForm(forms.Form):
    email = forms.EmailField(
        label="Invite by email",
        widget=forms.EmailInput(attrs={"placeholder": "teammate@example.com"}),
    )
