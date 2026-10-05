from django import forms

from .models import Project


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Website relaunch", "autofocus": True}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class InviteForm(forms.Form):
    email = forms.EmailField(
        label="Invite by email",
        widget=forms.EmailInput(attrs={"placeholder": "teammate@example.com"}),
    )
