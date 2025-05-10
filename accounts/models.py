# accounts/models.py
from django.db import models
from django.conf import settings

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    def __str__(self):
        return f"{self.user.username}'s Profile"

class SavedLocation(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='saved_locations')
    location_name = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    is_default = models.BooleanField(default=False)

    # --- Define choices and constants as class attributes BEFORE the field that uses them ---
    LOCATION_TYPE_HOME = 'home'
    LOCATION_TYPE_WORK = 'work'
    LOCATION_TYPE_SCHOOL = 'school'
    LOCATION_TYPE_VACATION = 'vacation'
    LOCATION_TYPE_RELATIVE = 'relative'
    LOCATION_TYPE_OTHER = 'other' # This constant will be used for the default

    LOCATION_TYPE_CHOICES = [
        (LOCATION_TYPE_HOME, 'Home'),
        (LOCATION_TYPE_WORK, 'Work'),
        (LOCATION_TYPE_SCHOOL, 'School'),
        (LOCATION_TYPE_VACATION, 'Vacation Spot'),
        (LOCATION_TYPE_RELATIVE, "Relative's House"),
        (LOCATION_TYPE_OTHER, 'Other'),
    ]

    location_type_label = models.CharField(
        max_length=20,
        choices=LOCATION_TYPE_CHOICES,    # <-- Refer directly to the class attribute
        default=LOCATION_TYPE_OTHER,      # <-- Refer directly to the class attribute
        blank=False,
        null=False,
        verbose_name="Location Label"
    )
    receive_notifications = models.BooleanField(default=True,
                                              help_text="Receive push notifications for alerts at this location")
    # --- End new field ---

    class Meta:
        ordering = ['pk']

    def __str__(self):
        default_status = " (Default)" if self.is_default else ""
        type_display = self.get_location_type_label_display() # This method is provided by Django for fields with choices
        notif_status = " (Alerts ON)" if self.receive_notifications else " (Alerts OFF)"
        return f"{self.location_name} ({type_display}){default_status}{notif_status} (for {self.profile.user.username})"
