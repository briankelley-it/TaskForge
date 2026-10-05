from django import forms
from django.contrib.auth import get_user_model

from projects.models import Project

from .models import Task

User = get_user_model()


class MemberChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj) -> str:
        return obj.name


class TaskForm(forms.ModelForm):
    assignee = MemberChoiceField(queryset=User.objects.none(), required=False)

    class Meta:
        model = Task
        fields = ["title", "description", "status", "priority", "due_date", "assignee"]
        widgets = {
            "title": forms.TextInput(attrs={"autofocus": True, "placeholder": "What needs doing?"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, project: Project, **kwargs):
        super().__init__(*args, **kwargs)
        # Only people in this project can be assigned. This also stops a crafted POST
        # from assigning an outsider.
        self.fields["assignee"].queryset = project.members.order_by("display_name", "email")
