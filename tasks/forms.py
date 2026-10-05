from django import forms
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.utils import timezone

from projects.models import Project

from .models import Comment, Task

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


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
        labels = {"body": "Add a comment"}
        widgets = {"body": forms.Textarea(attrs={"rows": 2, "placeholder": "Write a comment…"})}


class BoardFilterForm(forms.Form):
    """The filter bar above the board. Read from the query string, so a filtered board
    has its own URL that can be bookmarked or shared."""

    q = forms.CharField(required=False, label="Search")
    mine = forms.BooleanField(required=False, label="My tasks")
    overdue = forms.BooleanField(required=False, label="Overdue")
    priority = forms.ChoiceField(
        required=False, choices=[("", "Any priority"), *Task.Priority.choices]
    )

    def apply(self, tasks: QuerySet[Task], user) -> QuerySet[Task]:
        # An invalid value (say ?priority=urgent) is ignored rather than causing an error;
        # cleaned_data still holds every field that was valid.
        self.is_valid()
        data = self.cleaned_data
        if data.get("q"):
            tasks = tasks.filter(title__icontains=data["q"].strip())
        if data.get("mine"):
            tasks = tasks.filter(assignee=user)
        if data.get("overdue"):
            tasks = tasks.filter(due_date__lt=timezone.localdate()).exclude(status=Task.Status.DONE)
        if data.get("priority"):
            tasks = tasks.filter(priority=data["priority"])
        return tasks

    @property
    def is_filtering(self) -> bool:
        self.is_valid()
        return any(self.cleaned_data.get(name) for name in self.fields)
