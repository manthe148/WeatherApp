# weather/views.py
import os
import json
import traceback
from django.shortcuts import render, redirect
from django.conf import settings
import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import JsonResponse
from datetime import datetime, timedelta, timezone as python_dt_timezone # Alias for datetime.timezone
from django.utils import timezone as django_utils_tz # Alias for django.utils.timezone

# Your other imports
from .grib_processing import get_gfs_image_details_with_fallback, get_latest_nam_rundate_and_hour
from subscriptions.models import Subscription # Assuming this is your model
from subscriptions.tasks import fetch_alerts_by_zone_or_point # Assuming this is where it is

# --- Configuration Dictionaries ---
AVAILABLE_GFS_PARAMETERS_CONFIG = {
    't2m': {'name_display': '2m Temperature', 'output_file_prefix': 'gfs_t2m'},
    'sbcape': {'name_display': 'Surface CAPE', 'output_file_prefix': 'gfs_sbcape'},
    'refc': {'name_display': 'Sim. Comp. Reflectivity', 'output_file_prefix': 'gfs_refc'}
}

AVAILABLE_NAM_PARAMETERS_CONFIG = {
    'refc': {'name_display': 'Sim. Comp. Reflectivity', 'output_file_prefix': 'nam_refc'},
    'sbcape': {'name_display': 'Surface CAPE', 'output_file_prefix': 'nam_sbcape'},
    'dewp2m': {'name_display': 'NAM 2m Dew Point', 'output_file_prefix': 'nam_dewp2m'},
    'scp': {'name_display': 'NAM Supercell Composite', 'output_file_prefix': 'nam_scp'},
    'stp': {'name_display': 'NAM Sig. Tornado Param.', 'output_file_prefix': 'nam_stp'},

}

# --- Your get_weather_alerts function (from response #316) ---
# Make sure all its imports and helper calls are correct.
def get_weather_alerts(request):
    site_default_lat = Decimal("36.44")
    site_default_lon = Decimal("-95.28")
    site_default_name = "Adair, OK (Site Default)"
    current_latitude = site_default_lat
    current_longitude = site_default_lon
    current_location_name = site_default_name
    alerts_for_text_display = []
    raw_alert_features = [] 
    error_message = None
    source_of_location = "Site Default" 
    location_query = request.GET.get('location_query', '').strip()
    admin_email_for_ua = "default_email@example.com"
    try:
        if hasattr(settings, 'PUSH_NOTIFICATIONS_SETTINGS') and \
           isinstance(settings.PUSH_NOTIFICATIONS_SETTINGS.get("WP_CLAIMS"), dict) and \
           settings.PUSH_NOTIFICATIONS_SETTINGS["WP_CLAIMS"].get("sub"):
            admin_email_for_ua = settings.PUSH_NOTIFICATIONS_SETTINGS["WP_CLAIMS"]["sub"]
        else: print("  Warning: VAPID admin email for User-Agent not found in settings, using fallback.")
    except Exception as e_settings: print(f"  Warning: Error accessing VAPID email from settings: {e_settings}. Using fallback.")
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
            else: print(f"  User authenticated but no explicit default location. Using site default.")
        except Exception as e: print(f"  Error getting user's default: {e}. Using site default.")
    else: print(f"  No query, and user not authenticated or no profile/default. Using site default: {current_location_name}")
    nws_headers = {'User-Agent': f'MyWeatherApp/1.0 (AlertsPage NWS Call, {admin_email_for_ua})','Accept': 'application/geo+json'}
    target_alert_zone = get_nws_zone_for_coords(current_latitude, current_longitude, nws_headers['User-Agent'])
    raw_alert_features = fetch_alerts_by_zone_or_point(target_alert_zone, current_latitude, current_longitude, nws_headers['User-Agent'])
    if raw_alert_features:
        print(f"  DEBUG: Number of raw alert features received from API: {len(raw_alert_features)}")
        for i, feature_debug in enumerate(raw_alert_features):
            print(f"    Alert {i+1}: Event='{feature_debug.get('properties', {}).get('event', 'N/A')}', HasGeometry={'Yes' if feature_debug.get('geometry') else 'No'}")
        for alert_feature in raw_alert_features:
            props = alert_feature.get('properties', {})
            alerts_for_text_display.append({'id': props.get('id'), 'event': props.get('event', 'Weather Alert'),'headline': props.get('headline', 'N/A'),'severity': props.get('severity'),'description': props.get('description', '').replace('\n', '<br>')})
        if not raw_alert_features and not error_message: messages.info(request, f"No active NWS alerts for {current_location_name}.")
    else: print(f"  No raw alert features returned by fetch_alerts_by_zone_or_point for '{current_location_name}'")
    context = {'alerts': alerts_for_text_display, 'error_message': error_message,'location_name': current_location_name, 'latitude': current_latitude,'longitude': current_longitude, 'location_query': location_query,'source_of_location': source_of_location,'alerts_geojson_json_for_map': json.dumps(raw_alert_features if raw_alert_features else [])}
    return render(request, 'weather/weather.html', context)

# Your weather_models_landing_view (from your #316 paste - assumed correct)
@login_required
def weather_models_landing_view(request):
    is_subscriber = False
    try:
        if hasattr(request.user, 'subscription') and request.user.subscription and request.user.subscription.is_active():
            is_subscriber = True
    except (AttributeError, Subscription.DoesNotExist): pass
    except Exception as e: print(f"Error checking subscription in weather_models_landing_view: {e}")
    if not is_subscriber and not request.user.is_superuser:
        messages.warning(request, "Access to Weather Models requires an active subscription.")
        return redirect('subscriptions:plan_selection')
    context = {
        'page_title': "Weather Models Selection",
        'gfs_page_ready': True,  # GFS page is ready
        'nam_page_ready': True,   # <<< SET NAM PAGE AS READY
        'hrrr_page_ready': False  # HRRR is still coming soon
    }
    return render(request, 'weather/weather_models_landing.html', context)

# Your gfs_model_page_view (from your #316 paste - now with corrected time logic)
@login_required
def gfs_model_page_view(request):
    is_subscriber = False # Initialize
    try:
        if hasattr(request.user, 'subscription') and request.user.subscription and request.user.subscription.is_active():
            is_subscriber = True
    except (AttributeError, Subscription.DoesNotExist): pass
    except Exception as e: print(f"Error checking subscription: {e}")

    if not is_subscriber and not request.user.is_superuser:
        messages.warning(request, "Access to GFS Models requires an active subscription.")
        return redirect('subscriptions:plan_selection')

    requested_param_code = request.GET.get('param', 't2m').strip().lower()
    initial_fhr_str = request.GET.get('fhr', '006').strip() 
    param_config = AVAILABLE_GFS_PARAMETERS_CONFIG.get(requested_param_code)
    if not param_config: 
        requested_param_code = 't2m' 
        param_config = AVAILABLE_GFS_PARAMETERS_CONFIG[requested_param_code]
    
    fhr_validated_str = "006"; fhr_validated_int = 6
    try: 
        fhr_int_val = int(initial_fhr_str)
        if 0 <= fhr_int_val <= 384:
            fhr_validated_str = f"{fhr_int_val:03d}"
            fhr_validated_int = fhr_int_val
    except ValueError: pass 

    image_info = get_gfs_image_details_with_fallback(fhr_validated_str, param_config['output_file_prefix'], print)
    
    param_name_display = param_config['name_display']
    run_dt_utc = image_info.get('run_datetime_utc')
    actual_fhr_str = image_info['actual_fhr']
    actual_fhr_int = int(actual_fhr_str) if actual_fhr_str and actual_fhr_str.isdigit() else 0

    formatted_run_time_local = "Run: N/A"; formatted_valid_time_local = "Valid: N/A"
    page_title_for_browser_tab = f"GFS {param_name_display}"; main_heading_text = f"GFS {param_name_display}"

    if run_dt_utc:
        run_dt_local = django_utils_tz.localtime(run_dt_utc) # CORRECTED
        formatted_run_time_local = run_dt_local.strftime("%b %d, %Y, %-I:%M %p %Z")
        valid_dt_utc = run_dt_utc + timedelta(hours=actual_fhr_int)
        valid_dt_local = django_utils_tz.localtime(valid_dt_utc) # CORRECTED
        formatted_valid_time_local = valid_dt_local.strftime("%b %d, %-I:%M %p %Z")
        page_title_for_browser_tab = f"GFS {param_name_display} - F{actual_fhr_str} ({image_info.get('actual_run_hour','')}Z)"
        main_heading_text = f"GFS {param_name_display} - F{actual_fhr_str}"
    
    status_message_display = image_info['display_message'] 
    if image_info['image_exists'] and run_dt_utc:
        status_message_display = f"Run: {formatted_run_time_local} | Forecast F{actual_fhr_str} Valid: {formatted_valid_time_local}"
    elif run_dt_utc:
        status_message_display = f"Image for F{actual_fhr_str} (Run: {formatted_run_time_local}, Valid: {formatted_valid_time_local}) not available."
    
    available_fhrs_list = [f"{h:03d}" for h in range(0, 121, 6)]
    parameter_options_for_template = [{'code': k, 'name': v['name_display']} for k, v in AVAILABLE_GFS_PARAMETERS_CONFIG.items()]

    context = {
        'page_title_initial': page_title_for_browser_tab,
        'model_main_heading_initial': main_heading_text,
        'model_image_url_initial': image_info['image_url'],
        'image_exists_initial': image_info['image_exists'],
        'status_message_initial': status_message_display,
        'formatted_run_time_local_initial': formatted_run_time_local,
        'formatted_valid_time_local_initial': formatted_valid_time_local,
        'current_fhr_initial': image_info['actual_fhr'], 
        'current_fhr_initial_int': actual_fhr_int,
        'current_param_code_initial': requested_param_code, 
        'available_fhrs': available_fhrs_list,
        'available_parameters': parameter_options_for_template, 
        'api_url_for_js': reverse('weather:api_gfs_model_data') 
    }
    return render(request, 'weather/gfs_model_page.html', context)

# Your get_gfs_model_api_data function (from your #316 paste - now with corrected time logic)
@login_required
def get_gfs_model_api_data(request):
    if not (hasattr(request.user, 'subscription') and request.user.subscription and request.user.subscription.is_active()) and not request.user.is_superuser:
        return JsonResponse({'error': 'Subscription required'}, status=403)

    requested_fhr = request.GET.get('fhr', '006').strip()
    requested_param_code = request.GET.get('param', 't2m').strip().lower()
    param_config = AVAILABLE_GFS_PARAMETERS_CONFIG.get(requested_param_code)
    if not param_config: return JsonResponse({'error': 'Invalid GFS parameter'}, status=400)

    image_info = get_gfs_image_details_with_fallback(requested_fhr, param_config['output_file_prefix'], print)
    
    param_name_display = param_config['name_display']
    run_dt_utc = image_info.get('run_datetime_utc')
    actual_fhr_str = image_info['actual_fhr']
    actual_fhr_int = int(actual_fhr_str) if actual_fhr_str and actual_fhr_str.isdigit() else 0

    formatted_run_time_local = "Run: N/A"; formatted_valid_time_local = "Valid: N/A"
    page_title_for_browser_tab = f"GFS {param_name_display}"; main_heading_text = f"GFS {param_name_display}"

    if run_dt_utc:
        run_dt_local = django_utils_tz.localtime(run_dt_utc) # CORRECTED
        formatted_run_time_local = run_dt_local.strftime("%b %d, %Y, %-I:%M %p %Z")
        valid_dt_utc = run_dt_utc + timedelta(hours=actual_fhr_int)
        valid_dt_local = django_utils_tz.localtime(valid_dt_utc) # CORRECTED
        formatted_valid_time_local = valid_dt_local.strftime("%b %d, %-I:%M %p %Z")
        page_title_for_browser_tab = f"GFS {param_name_display} - F{actual_fhr_str} ({image_info.get('actual_run_hour','')}Z)"
        main_heading_text = f"GFS {param_name_display} - F{actual_fhr_str}"
    
    status_message_display = image_info['display_message']
    if image_info['image_exists'] and run_dt_utc:
        status_message_display = f"Run: {formatted_run_time_local} | Forecast F{actual_fhr_str} Valid: {formatted_valid_time_local}"
    elif run_dt_utc:
        status_message_display = f"Image for F{actual_fhr_str} (Run: {formatted_run_time_local}, Valid: {formatted_valid_time_local}) not available."
    
    data_to_return = {
        'image_exists': image_info['image_exists'], 'image_url': image_info['image_url'],
        'status_message': status_message_display, 'page_title': page_title_for_browser_tab,
        'main_heading': main_heading_text,
        'formatted_run_time_local': formatted_run_time_local, 
        'formatted_valid_time_local': formatted_valid_time_local, 
        'current_fhr': image_info['actual_fhr'], 'current_param_code': requested_param_code 
    }
    return JsonResponse(data_to_return)


# --- NAM Model Views ---
@login_required
def nam_model_page_view(request):
    is_subscriber = False # <<< INITIALIZE is_subscriber
    try:
        if hasattr(request.user, 'subscription') and request.user.subscription and request.user.subscription.is_active():
            is_subscriber = True
    except (AttributeError, Subscription.DoesNotExist): pass
    except Exception as e: print(f"Error checking subscription in nam_model_page_view: {e}")

    if not is_subscriber and not request.user.is_superuser:
        messages.warning(request, "Access to NAM Model data requires an active subscription.")
        return redirect('subscriptions:plan_selection')

    requested_param_code = request.GET.get('param', 'refc').strip().lower()
    initial_fhr_str = request.GET.get('fhr', '00').strip()
    
    param_config = AVAILABLE_NAM_PARAMETERS_CONFIG.get(requested_param_code)
    if not param_config: 
        messages.warning(request, f"Invalid NAM parameter '{requested_param_code}'. Defaulting to Reflectivity.")
        requested_param_code = 'refc' 
        param_config = AVAILABLE_NAM_PARAMETERS_CONFIG[requested_param_code]
    
    fhr_validated_str = "00"; fhr_validated_int = 0
    try: 
        fhr_int_val = int(initial_fhr_str)
        if 0 <= fhr_int_val <= 84:
            fhr_validated_str = f"{fhr_int_val:02d}"
            fhr_validated_int = fhr_int_val
    except ValueError: pass 

    nam_run_date_str, nam_model_run_hour_str = get_latest_nam_rundate_and_hour(print) # From grib_processing
    
    # Directly determine image existence and details for THIS run for NAM
    expected_nam_image_filename = f"{param_config['output_file_prefix']}_{nam_run_date_str}_{nam_model_run_hour_str}z_f{fhr_validated_str}.png"
    nam_image_fs_path = os.path.join(settings.MEDIA_ROOT, 'model_plots', expected_nam_image_filename)
    nam_image_url = settings.MEDIA_URL + os.path.join('model_plots', expected_nam_image_filename)
    nam_image_exists = os.path.exists(nam_image_fs_path)

    run_datetime_utc = None
    try:
        run_datetime_utc = datetime(
            int(nam_run_date_str[:4]), int(nam_run_date_str[4:6]), int(nam_run_date_str[6:8]),
            int(nam_model_run_hour_str), 
            tzinfo=python_dt_timezone.utc # CORRECTED ALIAS
        )
    except ValueError:
        print(f"Error parsing run datetime for NAM: {nam_run_date_str} {nam_model_run_hour_str}Z")
    
    param_name_display = param_config['name_display']
    formatted_run_time_local = "Run: N/A"; formatted_valid_time_local = "Valid: N/A"
    page_title_for_browser_tab = f"NAM {param_name_display}"; main_heading_text = f"NAM {param_name_display}"

    if run_datetime_utc:
        run_dt_local = django_utils_tz.localtime(run_datetime_utc) # CORRECTED ALIAS
        formatted_run_time_local = run_dt_local.strftime("%b %d, %Y, %-I:%M %p %Z")
        actual_fhr_int_for_calc = fhr_validated_int 
        valid_dt_utc = run_datetime_utc + timedelta(hours=actual_fhr_int_for_calc)
        valid_dt_local = django_utils_tz.localtime(valid_dt_utc) # CORRECTED ALIAS
        formatted_valid_time_local = valid_dt_local.strftime("%b %d, %-I:%M %p %Z")
        page_title_for_browser_tab = f"NAM {param_name_display} - F{fhr_validated_str} ({nam_model_run_hour_str}Z)"
        main_heading_text = f"NAM {param_name_display} - F{fhr_validated_str}"
    
    status_message_display = f"Image for NAM {param_name_display} F{fhr_validated_str} (Run: {formatted_run_time_local if run_datetime_utc else 'N/A'}, Valid: {formatted_valid_time_local if run_datetime_utc else 'N/A'}) not available."
    if nam_image_exists and run_datetime_utc:
        status_message_display = f"Run: {formatted_run_time_local} | Forecast F{fhr_validated_str} Valid: {formatted_valid_time_local}"
    
    available_fhrs_list_nam = [f"{h:02d}" for h in range(0,37)] + [f"{h:02d}" for h in range(39, 85, 3)]
    parameter_options_for_template_nam = [{'code': k, 'name': v['name_display']} for k, v in AVAILABLE_NAM_PARAMETERS_CONFIG.items()]

    context = {
        'model_name': "NAM", 
        'page_title_initial': page_title_for_browser_tab,
        'model_main_heading_initial': main_heading_text,
        'model_image_url_initial': nam_image_url if nam_image_exists else None,
        'image_exists_initial': nam_image_exists,
        'status_message_initial': status_message_display,
        'formatted_run_time_local_initial': formatted_run_time_local,
        'formatted_valid_time_local_initial': formatted_valid_time_local,
        'current_fhr_initial': fhr_validated_str, 
        'current_fhr_initial_int': fhr_validated_int,
        'current_param_code_initial': requested_param_code, 
        'available_fhrs': available_fhrs_list_nam,
        'available_parameters': parameter_options_for_template_nam, 
        'api_url_for_js': reverse('weather:api_nam_model_data') # URL for NAM API
    }
    return render(request, 'weather/nam_model_page.html', context) # Ensure this template exists

@login_required
def get_nam_model_api_data(request):
    # ... (Subscription check) ...
    if not (hasattr(request.user, 'subscription') and request.user.subscription and request.user.subscription.is_active()) and not request.user.is_superuser:
        return JsonResponse({'error': 'Subscription required'}, status=403)

    requested_fhr = request.GET.get('fhr', '00').strip()
    requested_param_code = request.GET.get('param', 'refc').strip().lower()

    param_config = AVAILABLE_NAM_PARAMETERS_CONFIG.get(requested_param_code)
    if not param_config: return JsonResponse({'error': 'Invalid NAM parameter'}, status=400)

    run_date_str, model_run_hour_str = get_latest_nam_rundate_and_hour(print)
    
    fhr_validated_str = "00"
    try:
        fhr_int_val = int(requested_fhr)
        if 0 <= fhr_int_val <= 84: fhr_validated_str = f"{fhr_int_val:02d}"
    except ValueError: pass
    
    expected_image_filename = f"{param_config['output_file_prefix']}_{run_date_str}_{model_run_hour_str}z_f{fhr_validated_str}.png"
    image_fs_path = os.path.join(settings.MEDIA_ROOT, 'model_plots', expected_image_filename)
    image_url_path = settings.MEDIA_URL + os.path.join('model_plots', expected_image_filename)
    image_exists = os.path.exists(image_fs_path)
    
    run_datetime_utc = None
    try:
        run_datetime_utc = datetime(int(run_date_str[:4]), int(run_date_str[4:6]), int(run_date_str[6:8]),
                                   int(model_run_hour_str), tzinfo=python_dt_timezone.utc) # CORRECTED
    except ValueError: pass

    param_name_display = param_config['name_display']
    formatted_run_time_local = "Run: N/A"; formatted_valid_time_local = "Valid: N/A"
    page_title_for_browser_tab = f"NAM {param_name_display}"; main_heading_text = f"NAM {param_name_display}"

    if run_datetime_utc:
        run_dt_local = django_utils_tz.localtime(run_datetime_utc) # CORRECTED
        formatted_run_time_local = run_dt_local.strftime("%b %d, %Y, %-I:%M %p %Z")
        actual_fhr_int_for_calc = int(fhr_validated_str) if fhr_validated_str.isdigit() else 0
        valid_dt_utc = run_datetime_utc + timedelta(hours=actual_fhr_int_for_calc)
        valid_dt_local = django_utils_tz.localtime(valid_dt_utc) # CORRECTED
        formatted_valid_time_local = valid_dt_local.strftime("%b %d, %-I:%M %p %Z")
        page_title_for_browser_tab = f"NAM {param_name_display} - F{fhr_validated_str} ({model_run_hour_str}Z)"
        main_heading_text = f"NAM {param_name_display} - F{fhr_validated_str}"
    
    status_message = f"Image for NAM {param_name_display} F{fhr_validated_str} not available."
    if image_exists and run_datetime_utc:
        status_message = f"Run: {formatted_run_time_local} | Forecast F{fhr_validated_str} Valid: {formatted_valid_time_local}"
    elif run_datetime_utc: # Image doesn't exist but we have run time
         status_message = f"Image for NAM {param_name_display} F{fhr_validated_str} (Run: {formatted_run_time_local}, Valid: {formatted_valid_time_local}) not available."

    data_to_return = {
        'image_exists': image_exists, 'image_url': image_url_path if image_exists else None,
        'status_message': status_message, 'page_title': page_title_for_browser_tab,
        'main_heading': main_heading_text,
        'formatted_run_time_local': formatted_run_time_local, 
        'formatted_valid_time_local': formatted_valid_time_local, 
        'current_fhr': fhr_validated_str, 'current_param_code': requested_param_code 
    }
    return JsonResponse(data_to_return)

@login_required
def premium_radar_view(request):
    # ... (Your existing premium_radar_view code from response #316) ...
    is_subscriber = False
    try:
        if hasattr(request.user, 'subscription') and request.user.subscription and request.user.subscription.is_active():
            is_subscriber = True
    except Exception as e:
        print(f"Error checking subscription for {request.user.username} in premium_radar_view: {e}")
        is_subscriber = False 

    if is_subscriber or request.user.is_superuser:
        context = {} 
        return render(request, 'weather/premium_radar.html', context)
    else:
        messages.warning(request, "Access to Premium Radar requires an active subscription.")
        return redirect('subscriptions:plan_selection')
