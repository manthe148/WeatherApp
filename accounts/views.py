# accounts/views.py

# Make sure all these imports are at the TOP of your file
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.db import transaction
from django.views.generic import TemplateView # <<< MAKE SURE THIS IS IMPORTED
from .models import Profile, SavedLocation
from subscriptions.models import Subscription
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from decimal import Decimal, InvalidOperation
import traceback
from django.contrib.auth import login # For sign_up view
from django.contrib.auth.forms import UserCreationForm # For sign_up view


# Keep your sign_up view and ServiceWorkerView class if they are in this file

class ServiceWorkerView(TemplateView):
    template_name = 'sw.js' # This should point to your project-level templates/sw.js
    content_type = 'application/javascript'
    # Optional: To ensure service worker can control root scope if served from /accounts/sw.js
    # def get_headers(self):
    #     headers = super().get_headers()
    #     headers['Service-Worker-Allowed'] = '/'
    #     return headers
# --- END ServiceWorkerView DEFINITION ---


# --- ADD THIS FUNCTION DEFINITION IF MISSING ---
def sign_up(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()  # Save the new user
            login(request, user)  # Log the user in
            # Redirect to the homepage or LOGIN_REDIRECT_URL
            # You can use a named URL here if you have one for home:
            # return redirect('pages:home') 
            return redirect('/')
        else:
            # Form was invalid, re-render signup page with errors
            return render(request, 'registration/signup.html', {'form': form})
    else:
        # Display an empty form for a GET request
        form = UserCreationForm()
        return render(request, 'registration/signup.html', {'form': form})

@login_required
def user_settings_view(request):
    profile = request.user.profile # Get user's profile

    # --- DEFINE is_subscriber and max_locations HERE (Available to both GET and POST) ---
    is_subscriber = False
    try:
        if hasattr(request.user, 'subscription') and request.user.subscription.is_active():
            is_subscriber = True
    except Subscription.DoesNotExist: # Be specific if this is the expected error
        is_subscriber = False
    except Exception as e: # Catch other potential errors during subscription check
        print(f"Error checking subscription status for {request.user.username}: {e}")
        is_subscriber = False # Default to false on error

    max_locations = 3 if is_subscriber else 1
    # --- END is_subscriber and max_locations DEFINITIONS ---

    if request.method == 'POST':
        geolocator = Nominatim(user_agent="my_django_weather_app_1.0_myemail@example.com") # Customize as needed

        # --- Handle Setting a Location as Default ---
        if 'make_default_location_id' in request.POST:
            location_id_to_make_default = request.POST.get('make_default_location_id')
            try:
                with transaction.atomic():
                    profile.saved_locations.update(is_default=False)
                    new_default_location = SavedLocation.objects.get(pk=location_id_to_make_default, profile=profile)
                    new_default_location.is_default = True
                    new_default_location.save()
                    messages.success(request, f"'{new_default_location.location_name}' is now your default location.")
            except SavedLocation.DoesNotExist:
                messages.error(request, "Selected location not found or permission denied.")
            except Exception as e:
                messages.error(request, f"Error setting default location: {e}")
                print(f"Error setting default: {e}")
            return redirect('accounts:settings')

        # --- Handle Deletion ---
        elif 'delete_location' in request.POST:
            location_id_to_delete = request.POST.get('delete_location')
            try:
                loc_to_delete = SavedLocation.objects.get(pk=location_id_to_delete, profile=profile)
                loc_name = loc_to_delete.location_name
                was_default = loc_to_delete.is_default
                loc_to_delete.delete()
                messages.success(request, f"Location '{loc_name}' deleted.")
                if was_default and profile.saved_locations.exists():
                    new_default = profile.saved_locations.all().order_by('pk').first()
                    if new_default:
                        new_default.is_default = True
                        new_default.save()
                        messages.info(request, f"'{new_default.location_name}' automatically set as new default.")
            except SavedLocation.DoesNotExist:
                messages.error(request, "Location not found or permission denied.")
            except (ValueError, TypeError):
                 messages.error(request, "Invalid location ID for deletion.")
            return redirect('accounts:settings')

        # --- ADD THIS ELIF BLOCK FOR TOGGLING NOTIFICATIONS ---
        elif 'toggle_notification_action' in request.POST: # Checks for the button name
            location_id_to_toggle = request.POST.get('toggle_notification_loc_id')
            print(f"DEBUG: Toggle notification action for loc_id: {location_id_to_toggle}")
            if location_id_to_toggle:
                try:
                    loc_to_toggle = SavedLocation.objects.get(pk=location_id_to_toggle, profile=profile)
                    loc_to_toggle.receive_notifications = not loc_to_toggle.receive_notifications # Toggle the boolean
                    loc_to_toggle.save()
                    status_text = "enabled" if loc_to_toggle.receive_notifications else "disabled"
                    messages.success(request, f"Alert notifications {status_text} for '{loc_to_toggle.location_name}'.")
                except SavedLocation.DoesNotExist:
                    messages.error(request, "Location not found or permission denied.")
                except Exception as e:
                    messages.error(request, f"Error toggling notification status: {e}")
                    print(f"Error toggling notifications: {e}")
            else:
                messages.error(request, "No location ID provided for toggling notifications.")
            return redirect('accounts:settings')
        # --- END TOGGLE NOTIFICATION BLOCK ---


        # --- Handle Manual Add ---
        elif 'add_manual_location' in request.POST:
            # `max_locations` is now in scope here
            current_location_count = profile.saved_locations.count()
            if current_location_count < max_locations:
                manual_query = request.POST.get('manual_location', '').strip()
                # Corrected line:
                location_type = request.POST.get('location_type_manual', 'other') # Use the string 'other' as default
                if manual_query:
                    try:
                        location = geolocator.geocode(manual_query, timeout=10, country_codes='us')
                        if location:
                            has_existing_default = profile.saved_locations.filter(is_default=True).exists()
                            make_this_new_location_default = not has_existing_default

                            SavedLocation.objects.create(
                                profile=profile,
                                location_name=location.address,
                                latitude=Decimal(location.latitude),
                                longitude=Decimal(location.longitude),
                                is_default=make_this_new_location_default,
                                location_type_label=location_type
                            )
                            messages.success(request, f"Location '{location.address}' ({location_type}) added.")
                            if make_this_new_location_default:
                                messages.info(request, f"'{location.address}' automatically set as default.")
                        else:
                            messages.error(request, f"Could not find coordinates for '{manual_query}'.")
                    except GeocoderTimedOut:
                        messages.error(request, "Geocoding service timed out while adding location. Please try again.")
                    except GeocoderServiceError as e:
                        messages.error(request, f"Geocoding service error while adding location: {e}")
                    except (ValueError, InvalidOperation) as e: # More specific for Decimal
                        messages.error(request, f"Invalid data for location coordinates: {e}")
                    except Exception as e:
                        messages.error(request, f"An unexpected error occurred while adding location: {e}")
                        print(f"Settings Manual Add - Geocoding/Save error: {e}")
                        traceback.print_exc()
                else:
                    messages.warning(request, "Please enter a location to add.")
            else:
                messages.error(request, f"You cannot add more than {max_locations} location(s).")
            return redirect('accounts:settings')

        # --- Handle Geolocation Add ---
        elif 'save_geo_location' in request.POST:
             # `max_locations` is now in scope here
             current_location_count = profile.saved_locations.count()
             if current_location_count < max_locations:
                lat_str = request.POST.get('geo_latitude')
                lon_str = request.POST.get('geo_longitude')
                location_type = request.POST.get('location_type_geo', 'other') # Use the string 'other' as default
                try:
                    lat = Decimal(lat_str)
                    lon = Decimal(lon_str)
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        raise ValueError("Invalid latitude or longitude range.")

                    location_name = f"Lat: {lat:.4f}, Lon: {lon:.4f}" # Fallback name
                    try:
                        reverse_location = geolocator.reverse((lat, lon), exactly_one=True, timeout=10)
                        if reverse_location:
                            location_name = reverse_location.address
                    except (GeocoderTimedOut, GeocoderServiceError, Exception) as e_rev_geo:
                         messages.warning(request, f"Reverse geocoding failed ({e_rev_geo}), saving coordinates only.")
                         print(f"Settings Page - Reverse Geocoding Error: {e_rev_geo}")

                    has_existing_default = profile.saved_locations.filter(is_default=True).exists()
                    make_this_new_location_default = not has_existing_default

                    SavedLocation.objects.create(
                        profile=profile,
                        location_name=location_name,
                        latitude=lat,
                        longitude=lon,
                        is_default=make_this_new_location_default,
                        location_type_label=location_type
                    )
                    messages.success(request, f"Current location '{location_name}' ({location_type}) added.")
                    if make_this_new_location_default:
                        messages.info(request, f"'{location_name}' automatically set as default.")
                except (InvalidOperation, TypeError, ValueError) as e_coords:
                    messages.error(request, f"Invalid coordinate data received from browser: {e_coords}.")
                    print(f"Settings Page - Geolocation coordinate error: Lat='{lat_str}', Lon='{lon_str}', Error: {e_coords}")
                except Exception as e_geo_main:
                    messages.error(request, f"An unexpected error occurred while saving geolocation: {e_geo_main}")
                    print(f"Settings Page - Geolocation Save General Error: {e_geo_main}")
                    if settings.DEBUG:
                        traceback.print_exc()
             else:
                 messages.error(request, f"You cannot add more than {max_locations} location(s).")
             return redirect('accounts:settings')

    # --- Handle GET Request (or after POST has redirected) ---
    # Re-fetch saved_locations for fresh data for the template
    saved_locations = profile.saved_locations.all().order_by('-is_default', 'pk') # Show default first
    # `max_locations` is already defined above. Now `can_add_location` will use it.
    can_add_location = saved_locations.count() < max_locations

    context = {
        'profile': profile,
        'saved_locations': saved_locations,
        'is_subscriber': is_subscriber,
        'can_add_location': can_add_location,
        'max_locations': max_locations,
        'vapid_public_key': settings.VAPID_PUBLIC_KEY_FOR_TEMPLATE,
        'location_type_choices': SavedLocation.LOCATION_TYPE_CHOICES # For the dropdown
    }
    return render(request, 'accounts/settings.html', context)
