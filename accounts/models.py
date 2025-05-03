from django.db import models
from django.conf import settings # Best practice for referring to User model

class Profile(models.Model):
    # Link to the built-in User model. Each User gets one Profile.
    # settings.AUTH_USER_MODEL refers to your active User model.
    # on_delete=models.CASCADE means if a User is deleted, their Profile is deleted too.
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    # Fields to store the default location - allow them to be empty initially
    default_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    default_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    default_location_name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        # String representation for admin site, etc.
        return f"{self.user.username}'s Profile"
