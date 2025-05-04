from django.shortcuts import render, redirect
from django.contrib.auth import login # Import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from decimal import Decimal, InvalidOperation
from .models import Profile, SavedLocation # Import BOTH models
from subscriptions.models import Subscription # Import Subscription model to check status
from django.shortcuts import get_object_or_404 # Helpful for getting objects or 404
import traceback # Keep for debugging
from django.conf import settings
from django.views.generic import TemplateView


# --- Ensure this class definition is present ---
class ServiceWorkerView(TemplateView):
    template_name = 'sw.js' # Make sure this points to templates/sw.js
    content_type = 'application/javascript'
    # We might add headers later if needed for scope, but keep it simple for now
# --- End class definition check ---


def sign_up(request):
    if request.method == 'POST':
        # Process submitted data
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save() # Save the new user object
            # Optional: Log the user in immediately after signup
            login(request, user)
            # Redirect to the homepage (or wherever LOGIN_REDIRECT_URL points)
            return redirect('/') # Or use redirect('pages:home')
        else:
            # Form was invalid, re-render with errors
            return render(request, 'registration/signup.html', {'form': form})
    else:
        # Display an empty form for a GET request
        form = UserCreationForm()
        return render(request, 'registration/signup.html', {'form': form})

@login_required
def user_settings_view(request):
    profile = request.user.profile
    saved_locations = profile.saved_locations.all().order_by('pk') # Get existing locations

    # --- Check subscription status ---
    is_subscriber = False
    try:
        # Check if the user has a subscription relation AND if it's active
        if hasattr(request.user, 'subscription') and request.user.subscription.is_active():
            is_subscriber = True
    except Subscription.DoesNotExist:
        # Handle case where signal might have failed or profile created before subscription app
        is_subscriber = False
    except Exception as e:
        print(f"Error checking subscription status for {request.user.username}: {e}")
        is_subscriber = False # Default to false on error

    # --- Determine Location Limits ---
    max_locations = 3 if is_subscriber else 1
    can_add_location = saved_locations.count() < max_locations

    # --- Handle POST Requests (Adding/Deleting Locations) ---
    if request.method == 'POST':
        geolocator = Nominatim(user_agent="my_django_weather_app_1.0_myemail@example.com") # Customize!

        # --- Handle Deletion ---
        if 'delete_location' in request.POST:
            location_id_to_delete = request.POST.get('delete_location')
            try:
                # Ensure the location exists and belongs to the current user's profile
                loc_to_delete = SavedLocation.objects.get(pk=location_id_to_delete, profile=profile)
                loc_name = loc_to_delete.location_name
                loc_to_delete.delete()
                messages.success(request, f"Location '{loc_name}' deleted.")
            except SavedLocation.DoesNotExist:
                messages.error(request, "Location not found or permission denied.")
            except (ValueError, TypeError):
                 messages.error(request, "Invalid location ID for deletion.")
            # Redirect after processing delete POST
            return redirect('accounts:settings')

        # --- Handle Manual Add ---
        elif 'add_manual_location' in request.POST:
            # Recalculate count in case one was just deleted
            if profile.saved_locations.count() < max_locations:
                manual_query = request.POST.get('manual_location', '').strip()
                if manual_query:
                    try:
                        location = geolocator.geocode(manual_query, timeout=10, country_codes='us')
                        if location:
                            SavedLocation.objects.create(
                                profile=profile,
                                location_name=location.address,
                                latitude=Decimal(location.latitude),
                                longitude=Decimal(location.longitude)
                            )
                            messages.success(request, f"Location '{location.address}' added.")
                        else:
                            messages.error(request, f"Could not find coordinates for '{manual_query}'.")
                    # Add specific geopy error handling back if needed...
                    except (GeocoderTimedOut, GeocoderServiceError, ValueError, Exception) as e:
                         messages.error(request, f"Geocoding error adding location: {e}")
                         print(f"Settings Manual Geocoding error: {e}")
                else:
                    messages.warning(request, "Please enter a location to add.")
            else:
                messages.error(request, f"You cannot add more than {max_locations} location(s).")
            # Redirect after processing add POST
            return redirect('accounts:settings')

        # --- Handle Geolocation Add ---
        elif 'save_geo_location' in request.POST:
             # Recalculate count
             if profile.saved_locations.count() < max_locations:
                lat_str = request.POST.get('geo_latitude')
                lon_str = request.POST.get('geo_longitude')
                try:
                    lat = Decimal(lat_str)
                    lon = Decimal(lon_str)
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        raise ValueError("Invalid lat/lon range.")

                    # Reverse geocode to get name
                    location_name = f"Lat: {lat:.4f}, Lon: {lon:.4f}" # Fallback
                    try:
                        reverse_location = geolocator.reverse((lat, lon), exactly_one=True, timeout=10)
                        if reverse_location:
                            location_name = reverse_location.address
                    except (GeocoderTimedOut, GeocoderServiceError, Exception) as e:
                         messages.warning(request, f"Reverse geocoding failed ({e}), saving coordinates only.")
                         print(f"Settings Reverse Geocoding Error: {e}")

                    # Create new SavedLocation
                    SavedLocation.objects.create(
                        profile=profile,
                        location_name=location_name,
                        latitude=lat,
                        longitude=lon
                    )
                    messages.success(request, f"Current location '{location_name}' added.")

                except (InvalidOperation, TypeError, ValueError) as e:
                    messages.error(request, f"Invalid coordinate data received: {e}.")
                    print(f"Settings Geolocation coordinate error: Lat='{lat_str}', Lon='{lon_str}', Error: {e}")
             else:
                 messages.error(request, f"You cannot add more than {max_locations} location(s).")
             # Redirect after processing geo POST
             return redirect('accounts:settings')

    # --- Handle GET Request ---
    # (Re-fetch locations in case one was just added/deleted before rendering)
    saved_locations = profile.saved_locations.all().order_by('pk')
    can_add_location = saved_locations.count() < max_locations # Recalculate for template

    context = {
        'profile': profile,
        'saved_locations': saved_locations,
        'is_subscriber': is_subscriber,
        'can_add_location': can_add_location,
        'max_locations': max_locations,
        'vapid_public_key': settings.VAPID_PUBLIC_KEY_FOR_TEMPLATE
    }

    print(f"--- DEBUG: VAPID key passed to template context: '{context.get('vapid_public_key')}' ---")
    return render(request, 'accounts/settings.html', context)
