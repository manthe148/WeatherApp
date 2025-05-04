from django.contrib import admin
from .models import Profile, SavedLocation # Add SavedLocation

# Keep existing Profile registration if you have one
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user',) # Or add other fields if needed

# Register SavedLocation
@admin.register(SavedLocation)
class SavedLocationAdmin(admin.ModelAdmin):
    list_display = ('location_name', 'profile', 'latitude', 'longitude')
    list_filter = ('profile__user',) # Filter by user
    search_fields = ('location_name', 'profile__user__username')
