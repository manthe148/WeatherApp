# accounts/models.py
from django.db import models
from django.conf import settings
import uuid


class UserLocationHistory(models.Model):
    """
    Stores periodic location updates for a user to check against weather alerts.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='location_history')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    # This flag will be updated by our background task
    is_in_warned_area = models.BooleanField(default=False) 

    def __str__(self):
        return f"Location for {self.user.username} at {self.timestamp}"

    class Meta:
        ordering = ['-timestamp'] # Order by most recent first
        verbose_name_plural = "User location histories"


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    seen_announcement_identifiers = models.JSONField(default=list, blank=True, help_text="List of unique identifiers of announcements seen by the user.")

    town = models.CharField(max_length=100, blank=True, null=True, help_text="User's town/city")
    state = models.CharField(max_length=50, blank=True, null=True, help_text="User's state/province (e.g., OK, Texas)") 

    def __str__(self):
        return f"{self.user.username}'s Profile"

    @property
    def has_premium_access(self):
        """
        Checks if the user has premium access for any reason.
        """
        print(f"--- [DEBUG] Checking has_premium_access for user: {self.user.username} ---")

        if self.user.is_superuser:
            print("[DEBUG] Access check: User is a superuser. -> ACCESS GRANTED")
            return True

        # This is the crucial check for your beta tester
        is_in_group = self.user.groups.filter(name='Beta Testers').exists()
        print(f"[DEBUG] Access check: User in 'Beta Testers' group? -> {is_in_group}")
        if is_in_group:
            print("[DEBUG] Access check: Access granted via Beta Testers group.")
            return True

        # This is the check for paying subscribers
        if hasattr(self.user, 'subscription') and self.user.subscription:
            is_sub_active = self.user.subscription.is_active()
            print(f"[DEBUG] Access check: User has an active subscription? -> {is_sub_active}")
            if is_sub_active:
                print("[DEBUG] Access check: Access granted via active subscription.")
                return True
        else:
            print("[DEBUG] Access check: User has no subscription object.")

        print("[DEBUG] --- No access conditions met. -> ACCESS DENIED ---")
        return False


class Family(models.Model):
    """
    Represents a group of users under a single family plan.
    """
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='owned_family',
        help_text="The primary user who owns the family plan subscription."
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name='families',
        blank=True,
        help_text="Users who have accepted an invitation to join this family."
    )
    name = models.CharField(max_length=100, help_text="e.g., 'The Smith Family'")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (Owner: {self.owner.username})"

    def get_member_count(self):
        # Counts members who have joined
        return self.members.count()


class FamilyInvitation(models.Model):
    """
    Stores and tracks invitations for users to join a family.
    """
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='invitations')
    email_to_invite = models.EmailField(help_text="Email address of the person being invited.")
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, # If inviter is deleted, invitation is deleted
        related_name='sent_invitations'
    )

    # A unique token for the invitation link
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_accepted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Invitation for {self.email_to_invite} to join {self.family.name}"




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
