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
from django.db import transaction

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

    # Check subscription status
    is_subscriber = False
    try:
        if hasattr(request.user, 'subscription') and request.user.subscription.is_active():
            is_subscriber = True
    except Exception as e:
        print(f"Error checking subscription status for {request.user.username}: {e}")
        is_subscriber = False

    max_locations = 3 if is_subscriber else 1

    # Handle POST Requests
    if request.method == 'POST':
        # Use a database transaction to ensure data integrity when setting default
        with transaction.atomic():
            profile = request.user.profile # Re-fetch profile just in case
            current_locations = profile.saved_locations.all()

            # --- Handle Setting Default ---
            if 'make_default_location' in request.POST:
                location_id_to_make_default = request.POST.get('make_default_location')
                try:
                    # Get the location selected by the user
                    new_default = current_locations.get(pk=location_id_to_make_default)
                    # Set all other locations for this profile to NOT be default
                    current_locations.exclude(pk=location_id_to_make_default).update(is_default=False)
                    # Set the selected one TO be default
                    new_default.is_default = True
                    new_default.save(update_fields=['is_default']) # Efficiently save only the changed field
                    messages.success(request, f"'{new_default.location_name}' set as default.")
                except SavedLocation.DoesNotExist:
                    messages.error(request, "Location not found or permission denied.")
                except (ValueError, TypeError):
                     messages.error(request, "Invalid location ID provided.")

            # --- Handle Deletion ---
            elif 'delete_location' in request.POST:
                location_id_to_delete = request.POST.get('delete_location')
                try:
                    loc_to_delete = current_locations.get(pk=location_id_to_delete)
                    loc_name = loc_to_delete.location_name
                    was_default = loc_to_delete.is_default
                    loc_to_delete.delete()
                    messages.success(request, f"Location '{loc_name}' deleted.")
                    # If the deleted one was default, make the first remaining one default
                    if was_default:
                        remaining_locations = profile.saved_locations.all().order_by('pk')
                        if remaining_locations.exists():
                            new_default = remaining_locations.first()
                            new_default.is_default = True
                            new_default.save(update_fields=['is_default'])
                            messages.info(request, f"'{new_default.location_name}' is now the default location.")
                except SavedLocation.DoesNotExist: messages.error(request, "Location not found or permission denied.")
                except (ValueError, TypeError): messages.error(request, "Invalid location ID for deletion.")

            # --- Handle Manual Add ---
            elif 'add_manual_location' in request.POST:
                current_count = current_locations.count() # Use count from already fetched locations
                if current_count < max_locations:
                    manual_query = request.POST.get('manual_location', '').strip()
                    if manual_query:
                        try:
                            geolocator = Nominatim(user_agent="my_django_weather_app_1.0_myemail@example.com")
                            location = geolocator.geocode(manual_query, timeout=10, country_codes='us')
                            if location:
                                # Set as default ONLY if it's the very first location
                                make_default = (current_count == 0)
                                new_loc = SavedLocation.objects.create(
                                    profile=profile, location_name=location.address,
                                    latitude=Decimal(location.latitude), longitude=Decimal(location.longitude),
                                    is_default=make_default
                                )
                                messages.success(request, f"Location '{location.address}' added.")
                                if make_default: messages.info(request, "First location automatically set as default.")
                            else: messages.error(request, f"Could not find coordinates for '{manual_query}'.")
                        except (GeocoderTimedOut, GeocoderServiceError, ValueError, Exception) as e:
                            messages.error(request, f"Geocoding error adding location: {e}")
                    else: messages.warning(request, "Please enter a location to add.")
                else: messages.error(request, f"Cannot add more than {max_locations} location(s).")

            # --- Handle Geolocation Add ---
            elif 'save_geo_location' in request.POST:
                 current_count = current_locations.count()
                 if current_count < max_locations:
                    lat_str = request.POST.get('geo_latitude'); lon_str = request.POST.get('geo_longitude')
                    try:
                        lat = Decimal(lat_str); lon = Decimal(lon_str)
                        if not (-90 <= lat <= 90 and -180 <= lon <= 180): raise ValueError("Invalid range.")
                        location_name = f"Lat: {lat:.4f}, Lon: {lon:.4f}" # Fallback
                        try:
                            geolocator = Nominatim(user_agent="my_django_weather_app_1.0_myemail@example.com")
                            reverse_location = geolocator.reverse((lat, lon), exactly_one=True, timeout=10)
                            if reverse_location: location_name = reverse_location.address
                        except Exception as e: messages.warning(request, f"Reverse geocoding failed ({e})")

                        make_default = (current_count == 0) # Default only if first location
                        SavedLocation.objects.create(
                            profile=profile, location_name=location_name,
                            latitude=lat, longitude=lon, is_default=make_default
                        )
                        messages.success(request, f"Current location '{location_name}' added.")
                        if make_default: messages.info(request, "First location automatically set as default.")
                    except (InvalidOperation, TypeError, ValueError) as e: messages.error(request, f"Invalid coordinate data: {e}.")
                 else: messages.error(request, f"Cannot add more than {max_locations} location(s).")

        # Always redirect after a POST to prevent resubmission on refresh
        return redirect('accounts:settings')

    # --- Handle GET Request ---
    saved_locations = profile.saved_locations.all().order_by('pk') # Re-fetch for display
    can_add_location = saved_locations.count() < max_locations

    context = {
        'profile': profile,
        'saved_locations': saved_locations,
        'is_subscriber': is_subscriber,
        'can_add_location': can_add_location,
        'max_locations': max_locations,
        'vapid_public_key': settings.VAPID_PUBLIC_KEY_FOR_TEMPLATE
    }
    return render(request, 'accounts/settings.html', context)

#    print(f"--- DEBUG: VAPID key passed to template context: '{context.get('vapid_public_key')}' ---")
    return render(request, 'accounts/settings.html', context)
