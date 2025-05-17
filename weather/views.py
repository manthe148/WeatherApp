import os, json
from django.shortcuts import render
from django.conf import settings
import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from subscriptions.tasks import get_nws_zone_for_coords, fetch_alerts_by_zone_or_point
from datetime import datetime, timedelta, timezone
from django.http import JsonResponse
from .grib_processing import get_gfs_image_details_with_fallback
from django.urls import reverse





# Import Profile model if needed (likely not directly needed here if accessing via user)
# from accounts.models import Profile


AVAILABLE_GFS_PARAMETERS_CONFIG = {
    't2m': { # Code used in URL and JS
        'name_display': '2m Temperature', # For display in buttons/titles
        'output_file_prefix': 'gfs_t2m',  # Matches prefix used by your task
    },
    'sbcape': {
        'name_display': 'Surface CAPE',
        'output_file_prefix': 'gfs_sbcape',
    },
    # Add 'refc' (Composite Reflectivity) here when its processing is ready
    'refc': {
        'name_display': 'Sim. Comp. Reflectivity',
        'output_file_prefix': 'gfs_refc',
    }
}

@login_required
def weather_models_view(request): # THIS IS THE VIEW FOR /weather/models/
    is_subscriber = False
    try:
        if hasattr(request.user, 'subscription') and request.user.subscription and request.user.subscription.is_active():
            is_subscriber = True
    except AttributeError: pass
    except Subscription.DoesNotExist: pass
    except Exception as e: print(f"Error checking subscription: {e}")

    if not is_subscriber and not request.user.is_superuser:
        messages.warning(request, "Access to Weather Models requires an active subscription.")
        return redirect('subscriptions:plan_selection')

    requested_param_code = request.GET.get('param', 't2m').strip().lower()
    initial_fhr = request.GET.get('fhr', '006').strip()

    param_config = AVAILABLE_GFS_PARAMETERS_CONFIG.get(requested_param_code)
    if not param_config: 
        requested_param_code = 't2m' 
        param_config = AVAILABLE_GFS_PARAMETERS_CONFIG[requested_param_code]

    try: 
        fhr_int = int(initial_fhr)
        initial_fhr = f"{fhr_int:03d}"
    except ValueError: initial_fhr = "006"

    image_info = get_gfs_image_details_with_fallback(
        initial_fhr, 
        param_config['output_file_prefix'], 
        print
    )

    page_title_for_display = f"GFS {param_config['name_display']} - F{image_info['actual_fhr']} (Run: {image_info['actual_run_date']} {image_info['actual_run_hour']}Z)"
    if not image_info['image_exists']:
        page_title_for_display = f"GFS {param_config['name_display']}"

    available_fhrs_list = [f"{h:03d}" for h in range(0, 121, 6)]

    parameter_options_for_template = [
        {'code': key, 'name': value['name_display']} 
        for key, value in AVAILABLE_GFS_PARAMETERS_CONFIG.items()
    ]

    context = {
        'page_title_initial': page_title_for_display,
        'model_image_url_initial': image_info['image_url'],
        'image_exists_initial': image_info['image_exists'],
        'status_message_initial': image_info['display_message'],
        'current_fhr_initial': image_info['actual_fhr'],
        'current_param_code_initial': requested_param_code, 
        'available_fhrs': available_fhrs_list,
        'available_parameters': parameter_options_for_template, 
        'api_url_for_js': reverse('weather:api_model_image_data') # Uses the name from urls.py
    }
    return render(request, 'weather/weather_models.html', context) # Template for this page

@login_required
def get_model_image_api_data(request): # THIS IS THE API VIEW
    if not (hasattr(request.user, 'subscription') and request.user.subscription and request.user.subscription.is_active()) and not request.user.is_superuser:
        return JsonResponse({'error': 'Subscription required'}, status=403)

    requested_fhr = request.GET.get('fhr', '006').strip()
    requested_param_code = request.GET.get('param', 't2m').strip().lower()

    param_config = AVAILABLE_GFS_PARAMETERS_CONFIG.get(requested_param_code)
    if not param_config:
        return JsonResponse({
            'error': 'Invalid parameter', 'image_exists': False,
            'status_message': f"Unknown parameter code '{requested_param_code}'.",
            'page_title': "Unknown Parameter", 'current_fhr': requested_fhr,
            'current_param_code': requested_param_code
        }, status=400)

    image_info = get_gfs_image_details_with_fallback(
        requested_fhr, 
        param_config['output_file_prefix'],
        print
    )

    page_title_detail = f"GFS {param_config['name_display']} - F{image_info['actual_fhr']} (Run: {image_info['actual_run_date']} {image_info['actual_run_hour']}Z)"
    if not image_info['image_exists']: page_title_detail = f"GFS {param_config['name_display']}"

    data_to_return = {
        'image_exists': image_info['image_exists'],
        'image_url': image_info['image_url'],
        'status_message': image_info['display_message'], 
        'page_title': page_title_detail, 
        'current_fhr': image_info['actual_fhr'],
        'current_param_code': requested_param_code 
    }
    return JsonResponse(data_to_return)


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
