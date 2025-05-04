from django.db import models
from django.conf import settings # Best practice for referring to User model

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # REMOVE these fields:
    # default_latitude = models.DecimalField(...)
    # default_longitude = models.DecimalField(...)
    # default_location_name = models.CharField(...)

    def __str__(self):
        return f"{self.user.username}'s Profile"

# --- ADD THIS NEW MODEL ---
class SavedLocation(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='saved_locations')
    location_name = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    # Optional: field to control display order
    # display_order = models.PositiveIntegerField(default=0)

    class Meta:
        # Optional: order locations by when they were added (primary key)
        ordering = ['pk']
        # Optional: prevent adding the exact same lat/lon twice for one user
        # unique_together = [['profile', 'latitude', 'longitude']]

    def __str__(self):
        # Show location name and associated user in Admin
        return f"{self.location_name} (for {self.profile.user.username})"
# --- END NEW MODEL ---
