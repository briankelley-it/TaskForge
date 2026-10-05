from django.contrib import admin

from .models import Activity


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ["created_at", "project", "actor", "verb", "target_title", "detail"]
    list_filter = ["verb", "project"]
    search_fields = ["target_title", "actor__email", "project__name"]
    list_select_related = ["project", "actor"]
    date_hierarchy = "created_at"
    # The feed is a historical record: read-only in the admin.
    readonly_fields = [f.name for f in Activity._meta.fields]

    def has_add_permission(self, request):
        return False
