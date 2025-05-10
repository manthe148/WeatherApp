from django.db import models
from django.utils import timezone

class SiteAnnouncement(models.Model):
    message = models.TextField(help_text="The content of the announcement/update message.")
    # A unique identifier for this announcement to track if users have seen it.
    # E.g., "v1.2-feature-location-labels"
    unique_identifier = models.CharField(max_length=100, unique=True,
                                       help_text="Unique ID for this announcement (e.g., 'update-2025-05-10')")
    is_active = models.BooleanField(default=True,
                                    help_text="Is this announcement currently active to be shown to users?")
    created_at = models.DateTimeField(auto_now_add=True)
    # Optional: Add an expiry date if announcements should automatically stop showing
    # expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Announcement: {self.unique_identifier} (Active: {self.is_active})"

    class Meta:
        ordering = ['-created_at'] # Show newest first in admin
