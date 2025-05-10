# pages/admin.py
from django.contrib import admin
from .models import SiteAnnouncement # Assuming SiteAnnouncement is in pages.models

@admin.register(SiteAnnouncement)
class SiteAnnouncementAdmin(admin.ModelAdmin):
    list_display = ('unique_identifier', 'message_summary', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('message', 'unique_identifier')
    readonly_fields = ('created_at',)

    def message_summary(self, obj):
        return obj.message[:75] + '...' if len(obj.message) > 75 else obj.message
    message_summary.short_description = 'Message'
