from django.contrib import admin
from .models import Profile, SavedLocation # Add SavedLocation

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
