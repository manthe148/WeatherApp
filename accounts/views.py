from django.shortcuts import render, redirect
from django.contrib.auth import login # Import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from decimal import Decimal, InvalidOperation

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

    if request.method == 'POST':
        geolocator = Nominatim(user_agent="my_django_weather_app_1.0_myemail@example.com") # Customize!

        # --- Handle Manual Location Form ---
        if 'save_manual_location' in request.POST:
            manual_query = request.POST.get('manual_location', '').strip()
            if manual_query:
                try:
                    location = geolocator.geocode(manual_query, timeout=10, country_codes='us')
                    if location:
                        profile.default_latitude = Decimal(location.latitude)
                        profile.default_longitude = Decimal(location.longitude)
                        profile.default_location_name = location.address
                        profile.save()
                        messages.success(request, f"Default location updated successfully to: {location.address}")
                    else:
                        messages.error(request, f"Could not find coordinates for '{manual_query}'. Location not updated.")
                # Keep existing geopy error handling...
                except GeocoderTimedOut:
                     messages.error(request, "Geocoding service timed out (Manual). Location not updated.")
                except GeocoderServiceError as e:
                     messages.error(request, f"Geocoding service error (Manual): {e}. Location not updated.")
                except Exception as e:
                     messages.error(request, f"An unexpected geocoding error occurred (Manual): {e}. Location not updated.")
                     print(f"Settings Manual Geocoding error: {e}")
            else:
                 messages.warning(request, "Manual location cannot be empty.")

        # --- Handle Browser Geolocation Form ---
        elif 'save_geo_location' in request.POST:
            lat_str = request.POST.get('geo_latitude')
            lon_str = request.POST.get('geo_longitude')

            try:
                # Validate and convert coordinates
                lat = Decimal(lat_str)
                lon = Decimal(lon_str)

                # Optional but good: basic range check
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError("Invalid latitude or longitude range.")

                # Reverse geocode to get a location name
                location_name = f"Lat: {lat:.4f}, Lon: {lon:.4f}" # Fallback name
                try:
                    # Increase timeout slightly for reverse geocode if needed
                    reverse_location = geolocator.reverse((lat, lon), exactly_one=True, timeout=10)
                    if reverse_location:
                        location_name = reverse_location.address
                except GeocoderTimedOut:
                     messages.warning(request, "Reverse geocoding timed out, saving coordinates only.")
                except GeocoderServiceError as e:
                     messages.warning(request, f"Reverse geocoding error: {e}, saving coordinates only.")
                except Exception as e: # Catch other potential reverse geocoding errors
                     messages.warning(request, f"Could not get address for coordinates: {e}. Saving coordinates only.")
                     print(f"Reverse Geocoding Error: {e}")


                # Save the coordinates and name
                profile.default_latitude = lat
                profile.default_longitude = lon
                profile.default_location_name = location_name
                profile.save()
                messages.success(request, f"Default location updated successfully to: {location_name}")

            except (InvalidOperation, TypeError, ValueError) as e:
                # Handle cases where lat/lon are not valid decimals or missing
                messages.error(request, f"Invalid coordinate data received from browser: {e}. Location not updated.")
                print(f"Geolocation coordinate error: Lat='{lat_str}', Lon='{lon_str}', Error: {e}")


        # Redirect back to settings page after processing any POST
        return redirect('accounts:settings')

    # --- Handle GET Request ---
    context = {
        'profile': profile
    }
    return render(request, 'accounts/settings.html', context)
