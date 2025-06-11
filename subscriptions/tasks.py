# subscriptions/tasks.py

import requests
from datetime import datetime, timezone
import traceback
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from push_notifications.models import WebPushDevice

# Assuming SavedLocation and Profile are in accounts.models
# Adjust if your Profile model is elsewhere or not directly used here
from accounts.models import SavedLocation, Profile
from .models import NotifiedAlert, Subscription # From subscriptions.models

User = get_user_model()

# --- Helper function to get NWS Zone ---
def get_nws_zone_for_coords(latitude, longitude, task_user_agent):
    """Helper to get the NWS county or forecast zone for given coordinates."""
    nws_points_url = f"https://api.weather.gov/points/{latitude},{longitude}"
    nws_headers = {'User-Agent': task_user_agent, 'Accept': 'application/geo+json'}
    target_alert_zone = None
    try:
        points_response = requests.get(nws_points_url, headers=nws_headers, timeout=10) # Shorter timeout for util
        points_response.raise_for_status()
        points_data = points_response.json()
        county_zone_url = points_data.get('properties', {}).get('county')
        if county_zone_url:
            target_alert_zone = county_zone_url.split('/')[-1]
        else: 
            forecast_zone_url = points_data.get('properties', {}).get('forecastZone')
            if forecast_zone_url:
                target_alert_zone = forecast_zone_url.split('/')[-1]
        return target_alert_zone
    except Exception as e:
        # print(f"NAVBAR_UTIL: Error getting NWS zone for ({latitude},{longitude}): {e}") # Optional: log differently
        return None


# --- Helper function to fetch alerts ---
def fetch_alerts_by_zone_or_point(zone_id, latitude, longitude, task_user_agent):
    """Fetches alerts by zone if zone_id is provided, otherwise by point as a fallback."""
    active_alerts_details = []
    nws_headers = {
        'User-Agent': task_user_agent,
        'Accept': 'application/geo+json'
    }

    if zone_id:
        nws_alerts_api_url = f"https://api.weather.gov/alerts/active?zone={zone_id}"
        fetch_method = f"ZONE {zone_id}"
    else:
        # Fallback to point query if zone_id couldn't be determined
        nws_alerts_api_url = f"https://api.weather.gov/alerts/active?point={latitude},{longitude}"
        fetch_method = f"POINT {latitude},{longitude}"
    
    print(f"  Fetching alerts using {fetch_method}: {nws_alerts_api_url}")
    
    try:
        alerts_response = requests.get(nws_alerts_api_url, headers=nws_headers, timeout=30) # Increased timeout
        alerts_response.raise_for_status()
        alerts_data_json = alerts_response.json()
        raw_alerts = alerts_data_json.get('features', [])
        for alert_feature in raw_alerts:
            props = alert_feature.get('properties', {})
            alert_detail = {
                'id': props.get('id'),
                'event': props.get('event', 'Weather Alert'),
                'headline': props.get('headline', 'Check weather app for details.'),
                'severity': props.get('severity')
                # Add other fields if needed, e.g., props.get('description')
            }
            if alert_detail['id']: # Only consider alerts that have an ID
                active_alerts_details.append(alert_detail)
        return active_alerts_details
    except requests.exceptions.RequestException as e:
        print(f"  NWS Alerts API Error for {fetch_method}: {e}")
    except Exception as e:
        print(f"  Error processing NWS alerts data for {fetch_method}: {e}")
        traceback.print_exc()
    return []

def check_weather_alerts_and_send_pushes():
    start_time = datetime.now(timezone.utc)
    print(f"[{start_time.isoformat()}] TASK_INFO: Running task: check_weather_alerts_and_send_pushes")

    admin_email_for_ua = getattr(settings, 'VAPID_ADMIN_EMAIL', "default_admin@example.com")
    if admin_email_for_ua.startswith("mailto:"): # Strip mailto if present from PUSH_NOTIFICATIONS_SETTINGS
        admin_email_for_ua = admin_email_for_ua[len("mailto:"):]
    
    app_name_display = getattr(settings, 'APP_NAME_DISPLAY', 'MyWeatherApp') 
    task_user_agent = f'{app_name_display}/1.0 (AlertCheckerTaskContact; {admin_email_for_ua})'

    users_to_check = User.objects.filter(
        Q(subscription__status__in=['active', 'trialing']) | Q(is_superuser=True),
        webpushdevice__active=True # Ensures user has at least one active push device
    ).distinct().prefetch_related(
        'profile__saved_locations', 
        'webpushdevice_set',      
        'subscription'            
    )

    print(f"TASK_INFO: Found {users_to_check.count()} user(s) with active push devices to check for alerts.")

    for user in users_to_check:
        print(f"\nTASK_INFO: Processing user: {user.username} (ID: {user.id})")
        
        is_subscriber = user.is_superuser
        if not is_subscriber:
            try:
                if hasattr(user, 'subscription') and user.subscription and user.subscription.is_active():
                    is_subscriber = True
            except Subscription.DoesNotExist:
                pass 
            except AttributeError: # If user.subscription doesn't exist
                print(f"  TASK_WARNING: User {user.username} has no 'subscription' attribute.")
            except Exception as e_sub_check:
                print(f"  TASK_ERROR: Error checking subscription status for {user.username}: {e_sub_check}")

        print(f"  TASK_INFO: User {user.username} is_subscriber status: {is_subscriber}")
        locations_to_monitor = []
        
        if hasattr(user, 'profile') and user.profile:
            if is_subscriber:
                locations_to_monitor = user.profile.saved_locations.filter(receive_notifications=True).order_by('pk')[:3]
                print(f"  TASK_INFO: Subscriber {user.username}: Checking {locations_to_monitor.count()} saved locations set for notifications (max 3).")
            else: 
                default_loc = user.profile.saved_locations.filter(is_default=True, receive_notifications=True).first()
                if default_loc:
                    locations_to_monitor = [default_loc]
                    print(f"  TASK_INFO: Free tier user {user.username}: Checking default location (alerts ON): {default_loc.location_name}")
                else:
                    print(f"  TASK_INFO: Free tier user {user.username}: No default location set for notifications.")
        else:
            print(f"  TASK_WARNING: User {user.username} has no profile or profile attribute.")

        if not locations_to_monitor:
            print(f"  TASK_INFO: No locations to monitor for {user.username}.")
            continue

        user_devices = user.webpushdevice_set.filter(active=True) # Get active devices again, just in case
        if not user_devices.exists(): # Should have been caught by initial users_to_check query, but good to double check
            print(f"  TASK_INFO: User {user.username} has no active push devices (re-checked). Skipping.")
            continue

        nws_alerts_pushed_this_session_for_user = set()

        for loc_instance in locations_to_monitor:
            print(f"  TASK_INFO: Checking location: {loc_instance.location_name} (Lat: {loc_instance.latitude}, Lon: {loc_instance.longitude}) for user {user.username}")
            
            zone_id = get_nws_zone_for_coords(loc_instance.latitude, loc_instance.longitude, task_user_agent)
            current_nws_alerts = fetch_alerts_by_zone_or_point(zone_id, loc_instance.latitude, loc_instance.longitude, task_user_agent)

            if not current_nws_alerts:
                print(f"    TASK_INFO: No active NWS alerts for {loc_instance.location_name}.")
                continue 

            for alert in current_nws_alerts:
                nws_alert_id = alert.get('id')
                if not nws_alert_id:
                    print("    TASK_WARNING: Skipping alert with no ID.")
                    continue 

                if nws_alert_id in nws_alerts_pushed_this_session_for_user:
                    print(f"    TASK_INFO: NWS ID {nws_alert_id} (event: {alert.get('event')}) already processed for {user.username} in this run for another of their locations.")
                    continue 

                if NotifiedAlert.objects.filter(user=user, nws_alert_id=nws_alert_id).exists():
                    print(f"    TASK_INFO: Alert {nws_alert_id} (event: {alert.get('event')}) already notified to {user.username} previously.")
                    continue 
                
                print(f"    TASK_INFO: NEW NWS Alert for {user.username}: {alert.get('event')} (ID: {nws_alert_id}) for saved location: {loc_instance.location_name}")
                
                click_url = "/weather/" 
                try:
                    # Ensure SITE_DOMAIN in settings.py is like "https://yourdomain.com" (no trailing slash)
                    click_url = f"{settings.SITE_DOMAIN.rstrip('/')}{reverse('weather:weather_page')}" # Ensure no double slashes
                except Exception as e_url:
                    print(f"    TASK_ERROR: Could not reverse 'weather:weather_page' URL for push: {e_url}. Using fallback URL '/'.")

                payload_dict = {
                    "head": f"{alert.get('event')} for: {loc_instance.location_type_label or loc_instance.location_name}",
                    "body": alert.get('headline', 'Check app for details.'),
                    "icon": settings.STATIC_URL.rstrip('/') + "/images/icons/Icon_192.png", 
                    "url": click_url,
                    "sound": settings.STATIC_URL.rstrip('/') + "/sounds/danger.mp3"  
                }
                json_string_payload = json.dumps(payload_dict)

                print(f"    TASK_INFO: Attempting to send push to {user.username} with payload: {json_string_payload}")

                # --- START: DEBUG BLOCK TO CHECK PUSH_NOTIFICATIONS_SETTINGS ---
                task_push_settings_dict_at_runtime = "PUSH_NOTIFICATIONS_SETTINGS_NOT_FOUND_ON_SETTINGS_OBJECT_IN_TASK"
                private_key_val_at_runtime = "PRIVATE_KEY_NOT_CHECKED_OR_FOUND_IN_TASK"
                
                print(f"    TASK_EXECUTION_DEBUG: --- Entering PUSH_NOTIFICATIONS_SETTINGS check in task for user {user.username} ---")
                if hasattr(settings, 'PUSH_NOTIFICATIONS_SETTINGS'):
                    task_push_settings_dict_at_runtime = settings.PUSH_NOTIFICATIONS_SETTINGS
                    print(f"    TASK_EXECUTION_DEBUG: settings.PUSH_NOTIFICATIONS_SETTINGS IS available to task.")
                    print(f"    TASK_EXECUTION_DEBUG: Type of settings.PUSH_NOTIFICATIONS_SETTINGS: {type(task_push_settings_dict_at_runtime)}")
                    print(f"    TASK_EXECUTION_DEBUG: Full settings.PUSH_NOTIFICATIONS_SETTINGS dict as seen by task: {task_push_settings_dict_at_runtime}") 
                    
                    if isinstance(task_push_settings_dict_at_runtime, dict):
                        if "VAPID_PRIVATE_KEY" in task_push_settings_dict_at_runtime: # Check for exact key string
                            private_key_val_at_runtime = task_push_settings_dict_at_runtime.get("VAPID_PRIVATE_KEY")
                            print(f"    TASK_EXECUTION_DEBUG: 'VAPID_PRIVATE_KEY' key IS IN dict. Value starts with: {str(private_key_val_at_runtime)[:20] if private_key_val_at_runtime else 'EMPTY or None'}")
                        else:
                            print(f"    TASK_EXECUTION_DEBUG: 'VAPID_PRIVATE_KEY' KEY IS MISSING from PUSH_NOTIFICATIONS_SETTINGS dict when checked by task!")
                    else:
                        print(f"    TASK_EXECUTION_DEBUG: settings.PUSH_NOTIFICATIONS_SETTINGS is not a dictionary when checked by task!")
                else:
                    print(f"    TASK_EXECUTION_DEBUG: settings.PUSH_NOTIFICATIONS_SETTINGS attribute itself IS MISSING when checked by task!")
                print(f"    TASK_EXECUTION_DEBUG: --- Finished PUSH_NOTIFICATIONS_SETTINGS check in task ---")
                # --- END: DEBUG BLOCK ---

                try:
                    # This is line 246 from your traceback in message #200
                    user_devices.send_message(json_string_payload) 
                    
                    NotifiedAlert.objects.create(
                        user=user,
                        nws_alert_id=nws_alert_id,
                        saved_location=loc_instance 
                    )
                    print(f"      TASK_SUCCESS: Push sent and DB record created for {user.username}, NWS ID {nws_alert_id} (Location: {loc_instance.location_name})")
                    nws_alerts_pushed_this_session_for_user.add(nws_alert_id)
                except Exception as e_send_message:
                    print(f"    TASK_ERROR: !!! FAILED to send push to {user.username} for NWS ID {nws_alert_id}: {e_send_message}")
                    print(f"    --- Traceback for push sending failure IN TASK (NWS ID: {nws_alert_id}): ---")
                    traceback.print_exc() # This prints the full traceback for the error
                    print(f"    --- End traceback for push sending failure IN TASK (NWS ID: {nws_alert_id}) ---")
        
        print(f"  TASK_INFO: Finished processing locations for {user.username}")

    end_time = datetime.now(timezone.utc)
    print(f"[{end_time.isoformat()}] TASK_INFO: Task finished. Duration: {end_time - start_time}")


#####################################################################################
def fetch_and_determine_alert_priority_for_navbar(latitude, longitude):
    """
    Fetches NWS alerts for a point and determines the highest priority status.
    Returns a dictionary: {'status': 'warning'|'watch'|'advisory'|None, 'count': int}
    """
    admin_email = "matt.mcdonald21@gmail.com" # Replace or get from settings
    if hasattr(settings, 'ADMIN_EMAIL_FOR_NWS_USER_AGENT'): # Create this setting if you want
        admin_email = settings.ADMIN_EMAIL_FOR_NWS_USER_AGENT
    
    user_agent_string = f"(UnfortunateNeighborApp/1.0 NavbarAlertCheck; {admin_email})"

    zone_id = _get_nws_zone_for_coords_util(latitude, longitude, user_agent_string)

    nws_alerts_api_url = ""
    if zone_id:
        nws_alerts_api_url = f"https://api.weather.gov/alerts/active?zone={zone_id}"
    else:
        nws_alerts_api_url = f"https://api.weather.gov/alerts/active?point={latitude},{longitude}"

    highest_priority_status = None
    alert_count = 0
    current_priority_level = 0  # 3: Warning, 2: Watch, 1: Advisory/Statement

    try:
        nws_headers = {'User-Agent': user_agent_string, 'Accept': 'application/geo+json'}
        response = requests.get(nws_alerts_api_url, headers=nws_headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        features = data.get('features', [])
        
        alert_count = len(features)
        if not features:
            return {'status': None, 'count': 0}

        for alert in features:
            properties = alert.get('properties', {})
            event_type = properties.get('event', '').lower()
            # NWS 'severity' can be: 'Extreme', 'Severe', 'Moderate', 'Minor', 'Unknown'
            # 'event' (like "Tornado Warning") is often more direct for W/W/A classification

            is_warning = 'warning' in event_type
            is_watch = 'watch' in event_type
            is_advisory = 'advisory' in event_type or 'statement' in event_type # e.g. Special Weather Statement

            if is_warning:
                if current_priority_level < 3:
                    highest_priority_status = 'warning'
                    current_priority_level = 3
            elif is_watch:
                if current_priority_level < 2:
                    highest_priority_status = 'watch'
                    current_priority_level = 2
            elif is_advisory:
                if current_priority_level < 1:
                    highest_priority_status = 'advisory'
                    current_priority_level = 1
            
    except requests.exceptions.RequestException as e:
        # print(f"NAVBAR_UTIL: Error fetching NWS alerts: {e}") # Optional: log differently
        return {'status': None, 'count': 0} 
    except json.JSONDecodeError as e:
        # print(f"NAVBAR_UTIL: Error decoding NWS JSON: {e}") # Optional: log differently
        return {'status': None, 'count': 0}
    
    return {'status': highest_priority_status, 'count': alert_count}


def get_user_navbar_alert_info(user):
    """
    Gets the NWS alert info for the user's default location for navbar display.
    Results are cached for 10 minutes.
    """
    if not user or not user.is_authenticated:
        return {'status': None, 'count': 0}

    cache_key = f"user_navbar_alert_info_{user.id}"
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        return cached_value

    alert_info_to_cache = {'status': None, 'count': 0} # Default

    # Accessing user's default location:
    # This needs to EXACTLY match your model structure.
    # Your tasks.py uses: user.profile.saved_locations.filter(is_default=True).first()
    default_location_obj = None
    if hasattr(user, 'profile') and user.profile:
        try:
            # Ensure your SavedLocation model is imported if using this directly
            # from accounts.models import SavedLocation 
            default_location_obj = user.profile.saved_locations.filter(is_default=True).first()
        except Exception as e:
            # print(f"NAVBAR_UTIL: Error getting default location for {user.username}: {e}")
            pass # default_location_obj remains None

    if default_location_obj:
        # print(f"NAVBAR_UTIL: Checking alerts for {user.username}'s default loc: {default_location_obj.location_name}")
        alert_info_to_cache = fetch_and_determine_alert_priority_for_navbar(
            default_location_obj.latitude,
            default_location_obj.longitude
        )
    else:
        # print(f"NAVBAR_UTIL: User {user.username} has no default location for navbar alerts.")
        pass

    cache.set(cache_key, alert_info_to_cache, 60 * 10) # Cache for 10 minutes
    return alert_info_to_cache


