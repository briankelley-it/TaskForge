from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "status", "priority", "assignee", "due_date", "position"]
    list_filter = ["status", "priority", "project"]
    search_fields = ["title", "description", "project__name"]
    list_select_related = ["project", "assignee"]
    autocomplete_fields = ["project", "assignee", "created_by"]
    date_hierarchy = "created_at"
