from django.shortcuts import render
from django.conf import settings
import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from subscriptions.tasks import get_nws_zone_for_coords, fetch_alerts_by_zone_or_point

# Import Profile model if needed (likely not directly needed here if accessing via user)
# from accounts.models import Profile

def get_weather_alerts(request):
    site_default_lat = Decimal("36.44")
    site_default_lon = Decimal("-95.28")
    site_default_name = "Adair, OK (Site Default)"

    current_latitude = site_default_lat
    current_longitude = site_default_lon
    current_location_name = site_default_name

    alerts_from_nws = []
    error_message = None
    source_of_location = "Site Default" # For debugging

    location_query = request.GET.get('location_query', '').strip()
    print(f"\n--- WEATHER PAGE (/weather/) ---")
    print(f"Received location_query: '{location_query}'")

    geolocator = Nominatim(user_agent=f"my_weather_app_geolocator/{settings.PUSH_NOTIFICATIONS_SETTINGS['WP_CLAIMS']['sub']}")

    if location_query:
        source_of_location = f"Query: {location_query}"
        try:
            location_obj_from_geopy = geolocator.geocode(location_query, timeout=10, country_codes='us')
            if location_obj_from_geopy:
                current_latitude = Decimal(location_obj_from_geopy.latitude)
                current_longitude = Decimal(location_obj_from_geopy.longitude)
                current_location_name = location_obj_from_geopy.address # Use this for map centering and display
                print(f"  Geopy SUCCESS for query: Found '{current_location_name}' at ({current_latitude}, {current_longitude})")
            else:
                error_message = f"Could not find coordinates for '{location_query}'. Displaying alerts for site default."
                print(f"  Geopy FAILED for query: No result. Using site defaults for map.")
                # Keep current_latitude etc. as site_default for map
        except (GeocoderTimedOut, GeocoderServiceError, Exception) as e:
            error_message = f"Geocoding error for '{location_query}': {e}. Displaying alerts for site default."
            print(f"  Geopy EXCEPTION for query: {e}. Using site defaults for map.")
            # Keep current_latitude etc. as site_default for map

    elif request.user.is_authenticated and hasattr(request.user, 'profile'):
        source_of_location = f"User Default for {request.user.username}"
        try:
            default_location_obj = request.user.profile.saved_locations.filter(is_default=True).first()
            if default_location_obj:
                current_latitude = default_location_obj.latitude
                current_longitude = default_location_obj.longitude
                current_location_name = default_location_obj.location_name
                source_of_location = f"User Default: {current_location_name}"
                print(f"  Using USER'S DEFAULT location: {current_location_name} ({current_latitude}, {current_longitude})")
            # else, site default is already set for current_latitude etc.
        except Exception as e:
            print(f"  Error getting user's default: {e}. Using site default for map.")
    # else, site default is already set for current_latitude etc.

    print(f"Coordinates for NWS /points/ API call: Lat={current_latitude}, Lon={current_longitude}")

    # --- Step 1: Get NWS Zone/County information for the coordinates ---
    nws_points_url = f"https://api.weather.gov/points/{current_latitude},{current_longitude}"
    admin_email_for_ua = settings.PUSH_NOTIFICATIONS_SETTINGS.get("WP_CLAIMS", {}).get("sub", "mailto:matt.mcdonald21@gmail.com")
    nws_headers = {
        'User-Agent': f'MyWeatherApp/1.0 (ViewAlerts, {admin_email_for_ua})',
        'Accept': 'application/geo+json' # Some NWS endpoints prefer this
    }

    target_alert_zone = None # This will be like 'LAC039' or 'LAZ032'

    try:
        points_response = requests.get(nws_points_url, headers=nws_headers, timeout=15)
        points_response.raise_for_status()
        points_data = points_response.json()

        # Try to get county zone first, then forecast zone
        county_zone_url = points_data.get('properties', {}).get('county')
        if county_zone_url:
            target_alert_zone = county_zone_url.split('/')[-1] # Extracts e.g., LAC039
            print(f"  Found NWS County Zone: {target_alert_zone} for {current_location_name}")
        else:
            forecast_zone_url = points_data.get('properties', {}).get('forecastZone')
            if forecast_zone_url:
                target_alert_zone = forecast_zone_url.split('/')[-1] # Extracts e.g., LAZ032
                print(f"  Found NWS Forecast Zone: {target_alert_zone} for {current_location_name}")
            else:
                print(f"  Could not find NWS county or forecast zone for {current_location_name}. Will try point query.")

    except requests.exceptions.RequestException as e:
        print(f"  Error calling NWS /points/ API: {e}. Will try point query for alerts.")
        if not error_message: error_message = "Could not retrieve zone information from NWS."
    except Exception as e:
        print(f"  Unexpected error processing NWS /points/ data: {e}. Will try point query.")
        if not error_message: error_message = "Error processing zone data."

    # --- Step 2: Fetch Alerts - by Zone if found, otherwise by Point ---
    if target_alert_zone:
        nws_alerts_api_url = f"https://api.weather.gov/alerts/active?zone={target_alert_zone}"
        print(f"  Fetching alerts using ZONE: {nws_alerts_api_url}")
    else:
        # Fallback to point query if zone not found or /points API failed
        nws_alerts_api_url = f"https://api.weather.gov/alerts/active?point={current_latitude},{current_longitude}"
        print(f"  Fetching alerts using POINT: {nws_alerts_api_url}")

    try:
        alerts_response = requests.get(nws_alerts_api_url, headers=nws_headers, timeout=20)
        alerts_response.raise_for_status()
        alerts_data_json = alerts_response.json()
        raw_alerts = alerts_data_json.get('features', [])
        for alert_feature in raw_alerts:
            props = alert_feature.get('properties', {})
            alerts_from_nws.append({
                'id': props.get('id'),
                'event': props.get('event', 'Weather Alert'),
                'headline': props.get('headline', 'Check weather app for details.'),
                'severity': props.get('severity'),
                'description': props.get('description', '').replace('\n', '<br>')
            })
        print(f"  Alerts received from NWS for '{current_location_name}' (via {target_alert_zone or 'point'}): {len(alerts_from_nws)} alerts")
    except requests.exceptions.RequestException as e:
        print(f"  NWS Alerts API Error: {e}")
        if not error_message: error_message = "Could not retrieve alerts from NWS."
    except Exception as e:
        print(f"  Error processing NWS alerts data: {e}")
        traceback.print_exc()
        if not error_message: error_message = "Error processing alert data."


    # Handle error messages if any
    if not target_alert_zone and not error_message: # If zone finding failed and no prior geo error
         error_message = "Could not determine NWS zone for alert lookup. Alerts shown may be for a precise point."
    if not alerts_from_nws and not error_message:
        # messages.info(request, f"No active NWS alerts for {current_location_name}.") # Optional
        pass


    context = {
        'alerts': alerts_from_nws,
        'error_message': error_message,
        'location_name': current_location_name, # This is still the geocoded name for map display
        'latitude': current_latitude,          # Geocoded latitude for map
        'longitude': current_longitude,        # Geocoded longitude for map
        'location_query': location_query,
        'source_of_location': source_of_location # For debugging display if needed
    }
    print(f"Context: location_name='{context['location_name']}', lat={context['latitude']}, lon={context['longitude']}")
    print(f"-------------------------------------\n")
    return render(request, 'weather/weather.html', context)

@login_required
def premium_radar_view(request):
    is_subscriber = False
    # Check subscription status safely
    try:
        if hasattr(request.user, 'subscription') and request.user.subscription.is_active():
             is_subscriber = True
    except Exception as e:
        print(f"Error checking subscription for {request.user.username} in premium_radar_view: {e}")
        is_subscriber = False # Default to false on error

    if is_subscriber:
        # User is active subscriber, render the premium page
        context = {} # Add any context needed for the premium radar later
        # Ensure this template path is correct
        return render(request, 'weather/premium_radar.html', context)
    else:
        # User is not an active subscriber, send message and redirect
        messages.warning(request, "Access to Premium Radar requires an active subscription.")
        # Redirect to the page where they can choose a plan
        return redirect('subscriptions:plan_selection')
