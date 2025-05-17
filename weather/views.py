import os, json, traceback
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

def get_weather_alerts(request):
    site_default_lat = Decimal("36.44")
    site_default_lon = Decimal("-95.28")
    site_default_name = "Adair, OK (Site Default)"

    current_latitude = site_default_lat
    current_longitude = site_default_lon
    current_location_name = site_default_name

    alerts_from_nws_api = [] # Raw alerts from API
    alerts_data_for_template = [] # Will hold properties + geometry
    error_message = None
    source_of_location = "Site Default" 

    location_query = request.GET.get('location_query', '').strip()
    print(f"\n--- ALERTS PAGE (/weather/) ---")
    print(f"Received location_query: '{location_query}'")

    admin_email_for_ua = "default_ua_email@example.com" # Fallback
    try:
        if hasattr(settings, 'PUSH_NOTIFICATIONS_SETTINGS') and \
           isinstance(settings.PUSH_NOTIFICATIONS_SETTINGS.get("WP_CLAIMS"), dict) and \
           settings.PUSH_NOTIFICATIONS_SETTINGS["WP_CLAIMS"].get("sub"):
            admin_email_for_ua = settings.PUSH_NOTIFICATIONS_SETTINGS["WP_CLAIMS"]["sub"]
    except Exception: pass

    geolocator = Nominatim(user_agent=f"my_weather_app_geolocator/{admin_email_for_ua}")

    if location_query:
        source_of_location = f"Query: {location_query}"
        try:
            location_obj_from_geopy = geolocator.geocode(location_query, timeout=10, country_codes='us')
            if location_obj_from_geopy:
                current_latitude = Decimal(location_obj_from_geopy.latitude)
                current_longitude = Decimal(location_obj_from_geopy.longitude)
                current_location_name = location_obj_from_geopy.address
                print(f"  Geopy SUCCESS for query: Found '{current_location_name}' at ({current_latitude}, {current_longitude})")
            else:
                error_message = f"Could not find coordinates for '{location_query}'. Displaying alerts for site default."
                print(f"  Geopy FAILED for query. Using site defaults for map.")
        except (GeocoderTimedOut, GeocoderServiceError, Exception) as e:
            error_message = f"Geocoding error for '{location_query}': {e}. Displaying site default."
            print(f"  Geopy EXCEPTION for query: {e}. Using site defaults for map.")

    elif request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile is not None:
        source_of_location = f"User Default for {request.user.username}"
        try:
            default_location_obj = request.user.profile.saved_locations.filter(is_default=True).first()
            if default_location_obj:
                current_latitude = default_location_obj.latitude
                current_longitude = default_location_obj.longitude
                current_location_name = default_location_obj.location_name
                source_of_location = f"User Default: {current_location_name}"
                print(f"  Using USER'S DEFAULT: {current_location_name} ({current_latitude}, {current_longitude})")
        except Exception as e:
            print(f"  Error getting user's default: {e}. Using site default.")
    else:
        print(f"No query, user not auth/profile. Using site default: {current_location_name}")

    print(f"Final coordinates for NWS API call: Lat={current_latitude}, Lon={current_longitude}")
    nws_headers = {'User-Agent': f'MyWeatherApp/1.0 (ViewAlerts, {admin_email_for_ua})', 'Accept': 'application/geo+json'}

    target_alert_zone = get_nws_zone_for_coords(current_latitude, current_longitude, nws_headers['User-Agent'])

    # Assuming fetch_alerts_by_zone_or_point returns the list of alert features with 'properties' and 'geometry'
    raw_nws_alert_features = fetch_alerts_by_zone_or_point(target_alert_zone, current_latitude, current_longitude, nws_headers['User-Agent'])

    if raw_nws_alert_features: # If it returned a list of features
        print(f"  Raw alert features from NWS: {len(raw_nws_alert_features)} features")
        for alert_feature in raw_nws_alert_features:
            props = alert_feature.get('properties', {})
            geometry = alert_feature.get('geometry') # This is the GeoJSON geometry

            alerts_data_for_template.append({
                'id': props.get('id'),
                'event': props.get('event', 'Weather Alert'),
                'headline': props.get('headline', 'Check weather app for details.'),
                'severity': props.get('severity'),
                'description': props.get('description', '').replace('\n', '<br>'),
                'geometry': geometry # Add the geometry here
            })
    else: # If fetch_alerts_by_zone_or_point returned None or empty due to error handled inside it
        print(f"  No raw alert features returned by fetch_alerts_by_zone_or_point for '{current_location_name}' (via {target_alert_zone or 'point'})")
        if not error_message: # If no prior geocoding error, set one for NWS API
             # This message will be shown if geocoding worked but NWS call failed or returned empty
             # error_message = f"No active alerts found for {current_location_name} via NWS API."
             pass # Or just let it show "No active alerts" based on empty list


    context = {
        'alerts': alerts_data_for_template, # This now contains geometry
        'error_message': error_message,
        'location_name': current_location_name,
        'latitude': current_latitude,
        'longitude': current_longitude,
        'location_query': location_query,
        'source_of_location': source_of_location,
        # Serialize alerts_data_for_template for JavaScript
        'alerts_geojson_json': json.dumps([a for a in alerts_data_for_template if a.get('geometry')]),
    }
    print(f"Context for weather.html: location_name='{context['location_name']}', alerts found: {len(alerts_data_for_template)}")
    print(f"-------------------------------------\n")
    return render(request, 'weather/weather.html', context)


@login_required
def weather_models_landing_view(request):
    is_subscriber = False
    try:
        if hasattr(request.user, 'subscription') and request.user.subscription and request.user.subscription.is_active():
            is_subscriber = True
    except AttributeError: pass # No 'subscription' attribute
    except Subscription.DoesNotExist: pass
    except Exception as e:
        print(f"Error checking subscription in weather_models_landing_view: {e}")

    if not is_subscriber and not request.user.is_superuser:
        messages.warning(request, "Access to Weather Models requires an active subscription.")
        return redirect('subscriptions:plan_selection')

    context = {
        'page_title': "Weather Models Selection"
    }
    return render(request, 'weather/weather_models_landing.html', context)


@login_required
def gfs_model_page_view(request): # THIS IS THE VIEW FOR /weather/models/
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
        'api_url_for_js': reverse('weather:api_gfs_model_data') # Uses the name from urls.py
    }
    return render(request, 'weather/gfs_model_page.html', context) # Template for this page

@login_required
def get_gfs_model_api_data(request): # THIS IS THE API VIEW
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


def get_weather_alerts(request): # This view is public
    site_default_lat = Decimal("36.44")
    site_default_lon = Decimal("-95.28")
    site_default_name = "Adair, OK (Site Default)"

    current_latitude = site_default_lat
    current_longitude = site_default_lon
    current_location_name = site_default_name

    alerts_for_text_display = [] # For the textual list of alerts
    raw_alert_features = []      # <<< INITIALIZE HERE for GeoJSON features for the map
    error_message = None
    source_of_location = "Site Default" 

    location_query = request.GET.get('location_query', '').strip()
    print(f"\n--- WEATHER PAGE (/weather/) ---")
    print(f"Received location_query: '{location_query}'")

    # User-Agent email setup
    admin_email_for_ua = "default_email@example.com" # Fallback
    try:
        if hasattr(settings, 'PUSH_NOTIFICATIONS_SETTINGS') and \
           isinstance(settings.PUSH_NOTIFICATIONS_SETTINGS.get("WP_CLAIMS"), dict) and \
           settings.PUSH_NOTIFICATIONS_SETTINGS["WP_CLAIMS"].get("sub"):
            admin_email_for_ua = settings.PUSH_NOTIFICATIONS_SETTINGS["WP_CLAIMS"]["sub"]
        else:
            print("  Warning: VAPID admin email for User-Agent not found in settings, using fallback.")
    except Exception as e_settings:
        print(f"  Warning: Error accessing VAPID email from settings: {e_settings}. Using fallback.")

    geolocator = Nominatim(user_agent=f"MyWeatherApp/1.0 Geocoder ({admin_email_for_ua})")

    if location_query:
        source_of_location = f"Query: {location_query}"
        try:
            location_obj_from_geopy = geolocator.geocode(location_query, timeout=10, country_codes='us')
            if location_obj_from_geopy:
                current_latitude = Decimal(location_obj_from_geopy.latitude)
                current_longitude = Decimal(location_obj_from_geopy.longitude)
                current_location_name = location_obj_from_geopy.address
                print(f"  Geopy SUCCESS for query: Found '{current_location_name}' at ({current_latitude}, {current_longitude})")
            else:
                error_message = f"Could not find coordinates for '{location_query}'. Displaying alerts for site default."
                print(f"  Geopy FAILED for query: No result. Using site defaults.")
        except (GeocoderTimedOut, GeocoderServiceError, Exception) as e:
            error_message = f"Geocoding error for '{location_query}': {e}. Displaying alerts for site default."
            print(f"  Geopy EXCEPTION for query: {e}.")
    
    elif request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile is not None:
        source_of_location = f"User Default for {request.user.username}"
        try:
            default_location_obj = request.user.profile.saved_locations.filter(is_default=True).first()
            if default_location_obj:
                current_latitude = default_location_obj.latitude
                current_longitude = default_location_obj.longitude
                current_location_name = default_location_obj.location_name
                source_of_location = f"User Default: {current_location_name}"
                print(f"  Using USER'S DEFAULT location: {current_location_name} ({current_latitude}, {current_longitude})")
            else:
                print(f"  User authenticated but no explicit default location. Using site default.")
        except Exception as e: # Catch specific exceptions like Profile.DoesNotExist if applicable
            print(f"  Error getting user's default: {e}. Using site default.")
    else:
        print(f"  No query, and user not authenticated or no profile/default. Using site default: {current_location_name}")

    print(f"Coordinates for NWS /points/ API call: Lat={current_latitude}, Lon={current_longitude}")
    nws_headers = {
        'User-Agent': f'MyWeatherApp/1.0 (AlertsPage NWS Call, {admin_email_for_ua})',
        'Accept': 'application/geo+json'
    }
    
    # Use the imported get_nws_zone_for_coords helper
    target_alert_zone = get_nws_zone_for_coords(current_latitude, current_longitude, nws_headers['User-Agent'])
    
    nws_alerts_api_url = ""
    fetch_method_for_log = ""
    if target_alert_zone:
        nws_alerts_api_url = f"https://api.weather.gov/alerts/active?zone={target_alert_zone}"
        fetch_method_for_log = f"ZONE {target_alert_zone}"
    else:
        nws_alerts_api_url = f"https://api.weather.gov/alerts/active?point={current_latitude},{current_longitude}"
        fetch_method_for_log = f"POINT {current_latitude},{current_longitude}"
    
    print(f"  Fetching NWS alerts using {fetch_method_for_log}: {nws_alerts_api_url}")

    try:
        alerts_response = requests.get(nws_alerts_api_url, headers=nws_headers, timeout=20)
        alerts_response.raise_for_status()
        alerts_data_json = alerts_response.json()
        
        # Assign to raw_alert_features (which was initialized as [] above)
        raw_alert_features = alerts_data_json.get('features', []) 
        
        # --- DEBUG: Print details of received raw alert features ---
        # This is inside the try block, after raw_alert_features is assigned
        print(f"  DEBUG: Number of raw alert features received from API: {len(raw_alert_features)}")
        for i, feature in enumerate(raw_alert_features): # Iterate over the correct variable
            event_name = feature.get('properties', {}).get('event', 'N/A Event')
            headline_text = feature.get('properties', {}).get('headline', 'N/A Headline')
            has_geometry = "Yes" if feature.get('geometry') else "No"
            print(f"    Alert {i+1}: Event='{event_name}', Headline='{headline_text[:60]}...', HasGeometry='{has_geometry}'")
        # --- END DEBUG ---
        
        # Process for text display (using raw_alert_features)
        for alert_feature in raw_alert_features: # Iterate over the correct list
            props = alert_feature.get('properties', {})
            alerts_for_text_display.append({ # Changed variable name here
                'id': props.get('id'),
                'event': props.get('event', 'Weather Alert'),
                'headline': props.get('headline', 'Check weather app for details.'),
                'severity': props.get('severity'),
                'description': props.get('description', '').replace('\n', '<br>')
            })
        
        print(f"  Alerts processed for text display: {len(alerts_for_text_display)}")
        if not raw_alert_features and not error_message: # If no alerts were fetched
             messages.info(request, f"No active NWS alerts found for {current_location_name}.")

    except requests.exceptions.RequestException as e:
        print(f"  NWS Alerts API Error: {e}")
        error_message = error_message or "Could not retrieve alerts from NWS at this time."
        # raw_alert_features will remain []
    except json.JSONDecodeError as e: # More specific error for JSON issues
        print(f"  Error decoding NWS alerts JSON data: {e}")
        traceback.print_exc()
        error_message = error_message or "Error processing alert data from NWS (JSON)."
    except Exception as e:
        print(f"  General error processing NWS alerts data: {e}")
        traceback.print_exc()
        error_message = error_message or "Error processing alert data."
        # raw_alert_features will remain []

    # Context preparation
    context = {
        'alerts': alerts_for_text_display, # Use the correctly populated list for text
        'error_message': error_message,
        'location_name': current_location_name,
        'latitude': current_latitude,
        'longitude': current_longitude,
        'location_query': location_query,
        'source_of_location': source_of_location,
        'alerts_geojson_json_for_map': json.dumps(raw_alert_features), # Use raw_alert_features
    }
    print(f"Context for weather.html: location_name='{context['location_name']}', alerts_for_text: {len(alerts_for_text_display)}, raw_features_for_map: {len(raw_alert_features)}")
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
