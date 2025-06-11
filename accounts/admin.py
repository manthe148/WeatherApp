from django.contrib import admin
from .models import Profile, SavedLocation, Family, FamilyInvitation, UserLocationHistory # Add SavedLocation
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin 
from django.contrib.auth.models import User



# You might have an existing ProfileInline
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'profile'

# You might have an existing UserAdmin
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)

# --- ADD THIS NEW CLASS ---
@admin.register(UserLocationHistory)
class UserLocationHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'timestamp', 'latitude', 'longitude', 'is_in_warned_area')
    list_filter = ('user', 'is_in_warned_area', 'timestamp')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('timestamp',) # Don't allow editing the timestamp
# --- END NEW CLASS ---


# Keep existing Profile registration if you have one
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user',) # Or add other fields if needed

# Register SavedLocation
@admin.register(SavedLocation)
class SavedLocationAdmin(admin.ModelAdmin):
    list_display = ('location_name', 'profile', 'location_type_label', 'is_default', 'receive_notifications', 'latitude', 'longitude') # Added receive_notifications
    list_filter = ('profile__user', 'is_default', 'location_type_label', 'receive_notifications') # Added
    search_fields = ('location_name', 'profile__user__username')
    actions = ['make_default']
