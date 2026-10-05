from django.contrib import admin

from .models import Comment, Task


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    autocomplete_fields = ["author"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "status", "priority", "assignee", "due_date", "position"]
    list_filter = ["status", "priority", "project"]
    search_fields = ["title", "description", "project__name"]
    list_select_related = ["project", "assignee"]
    autocomplete_fields = ["project", "assignee", "created_by"]
    date_hierarchy = "created_at"
    inlines = [CommentInline]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["task", "author", "created_at"]
    search_fields = ["body", "task__title", "author__email"]
    list_select_related = ["task", "author"]
    autocomplete_fields = ["task", "author"]
