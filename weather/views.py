from django.shortcuts import render
import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from decimal import Decimal, InvalidOperation
# Import Profile model if needed (likely not directly needed here if accessing via user)
# from accounts.models import Profile

def get_weather_alerts(request):
    """
    Fetches active weather alerts from the NWS API.
    Uses location from GET query parameter if provided.
    Otherwise, uses logged-in user's saved default location if available.
    Otherwise, uses a hardcoded site default location.
    """
    # Site default location (Adair, OK)
    site_default_lat = Decimal("36.44")
    site_default_lon = Decimal("-95.28")
    site_default_name = "Adair, OK"

    # Initialize with site defaults
    latitude = site_default_lat
    longitude = site_default_lon
    location_name = site_default_name
    error_message = None

    # Check for an explicit location query first
    location_query = request.GET.get('location_query', None)

    if location_query:
        # --- Geocode the explicit query ---
        geocoding_error = None
        try:
            geolocator = Nominatim(user_agent="my_django_weather_app_1.0_myemail@example.com") # Customize!
            location = geolocator.geocode(location_query, timeout=10, country_codes='us')
            if location:
                latitude = Decimal(location.latitude) # Use geocoded coords
                longitude = Decimal(location.longitude)
                location_name = location.address # Use geocoded name
            else:
                geocoding_error = f"Could not find coordinates for '{location_query}'. Using default location."
                # Fallback to site defaults if query fails
                latitude = site_default_lat
                longitude = site_default_lon
                location_name = site_default_name
        # Handle geopy exceptions...
        except (GeocoderTimedOut, GeocoderServiceError, Exception) as e:
             geocoding_error = f"Geocoding error for '{location_query}': {e}. Using default location."
             print(f"Weather View Geocoding error: {e}") # Log
             # Fallback to site defaults
             latitude = site_default_lat
             longitude = site_default_lon
             location_name = site_default_name

        if geocoding_error:
             error_message = geocoding_error # Show geocoding error

    elif request.user.is_authenticated:
        # --- No explicit query, check for logged-in user's saved default ---
        try:
            profile = request.user.profile # Access related profile
            if profile.default_latitude is not None and profile.default_longitude is not None:
                latitude = profile.default_latitude # Use profile coords
                longitude = profile.default_longitude
                # Use profile name, fallback to site default name if profile name is somehow empty
                location_name = profile.default_location_name or site_default_name
                print(f"Using saved location for user {request.user.username}: {location_name}") # Log
            # else: user has no saved default, so we just keep the site default initialized earlier
        except AttributeError:
            # This handles the case where request.user might not have a 'profile'
            # attribute, though signals should prevent this for logged-in users.
            print(f"Error accessing profile for user {request.user.username}")
            # Keep site default
        except Exception as e:
            print(f"Error retrieving profile default location: {e}")
            # Keep site default


    # --- Fetch NWS Alerts using determined coordinates (latitude, longitude) ---
    nws_api_url = f"https://api.weather.gov/alerts/active?point={latitude},{longitude}"
    headers = {
        'User-Agent': 'MyDjangoWeatherApp/1.0 (myemail@example.com)', # Customize!
        'Accept': 'application/geo+json'
    }
    alerts_data = []
    api_error = None

    # Make sure any dummy data logic is commented out for live testing
    # dummy_alerts_data = [ ... ]
    # alerts_data = dummy_alerts_data
    # error_message = None

    try:
        response = requests.get(nws_api_url, headers=headers, timeout=15) # Slightly increased timeout
        response.raise_for_status()
        data = response.json()
        raw_alerts = data.get('features', [])
        for alert in raw_alerts:
            properties = alert.get('properties', {})
            alerts_data.append({
                'headline': properties.get('headline', 'No Headline'),
                'event': properties.get('event', 'Unknown Event'),
                'severity': properties.get('severity', 'Unknown Severity'),
                'description': properties.get('description', 'No Description').replace('\n', '<br>'),
                'areaDesc': properties.get('areaDesc', 'Unknown Area').replace(';', '; '),
                'effective': properties.get('effective', 'N/A'),
                'expires': properties.get('expires', 'N/A'),
            })
    # Handle API exceptions...
    except requests.exceptions.Timeout:
        api_error = "The request to the NWS API timed out."
    except requests.exceptions.HTTPError as http_err:
        api_error = f"NWS API request failed: {http_err}"
    except requests.exceptions.RequestException as req_err:
        api_error = f"Could not connect to the NWS API: {req_err}"
    except Exception as e:
        api_error = f"An error occurred processing weather data: {e}"
        print(f"Error processing weather data: {e}")

    # Combine error messages if needed
    if api_error:
        error_message = f"{error_message}\n{api_error}" if error_message else api_error


    # Prepare context
    context = {
        'alerts': alerts_data,
        'error_message': error_message,
        'location_name': location_name, # The name determined by the logic above
        'location_query': location_query, # Pass back user's explicit query for the form
        'latitude': latitude, # Pass final coords used to the template
        'longitude': longitude,
    }

    return render(request, 'weather/weather.html', context)
