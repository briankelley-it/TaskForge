from django.contrib import admin

from .models import Membership, Project


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "created_at", "updated_at"]
    search_fields = ["name", "owner__email"]
    list_select_related = ["owner"]
    autocomplete_fields = ["owner"]
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["project", "user", "role", "joined_at"]
    list_filter = ["role"]
    search_fields = ["project__name", "user__email"]
    list_select_related = ["project", "user"]
    autocomplete_fields = ["project", "user"]
