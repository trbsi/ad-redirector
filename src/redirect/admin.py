from django.contrib import admin
from django.utils.html import format_html

from .models import Click, Link


@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    list_display = ["code", "visits", "created_at", "direct_link"]
    search_fields = ["code"]
    readonly_fields = ["visits", "created_at", "direct_link"]
    date_hierarchy = "created_at"

    @admin.display(description="Direct link")
    def direct_link(self, obj):
        if not obj.pk:
            return "Save the link to get its URL."
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>',
            obj.get_absolute_url(),
            obj.get_absolute_url(),
        )


@admin.register(Click)
class ClickAdmin(admin.ModelAdmin):
    list_display = ["created_at", "link", "ip"]
    list_filter = ["link"]
    list_select_related = ["link"]
    search_fields = ["link__code", "ip"]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
