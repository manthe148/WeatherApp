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

# --- Main Background Task Function ---
def check_weather_alerts_and_send_pushes():
    start_time = datetime.now(timezone.utc)
    print(f"[{start_time.isoformat()}] Running task: check_weather_alerts_and_send_pushes")

    admin_email_for_ua = "default_admin@example.com" # Fallback email
    try:
        # Ensure PUSH_NOTIFICATIONS_SETTINGS and its keys exist
        if hasattr(settings, 'PUSH_NOTIFICATIONS_SETTINGS') and \
           settings.PUSH_NOTIFICATIONS_SETTINGS.get("WP_CLAIMS") and \
           settings.PUSH_NOTIFICATIONS_SETTINGS["WP_CLAIMS"].get("sub"):
            admin_email_for_ua = settings.PUSH_NOTIFICATIONS_SETTINGS["WP_CLAIMS"]["sub"]
        else:
            print("  Warning: VAPID admin email not found in settings, using fallback for User-Agent.")
    except Exception as e:
        print(f"  Error accessing VAPID email from settings: {e}. Using fallback.")
    
    task_user_agent = f'MyWeatherApp/1.0 (AlertCheckerTask, {admin_email_for_ua})'

    # Get users with active subscriptions (or superusers) and active push devices
    users_to_check = User.objects.filter(
        Q(subscription__status__in=['active', 'trialing']) | Q(is_superuser=True),
        webpushdevice__active=True
    ).distinct().prefetch_related(
        'profile__saved_locations', # Assumes Profile is related to User as 'profile'
        'webpushdevice_set',        # Default related_name for ForeignKey from WebPushDevice to User
        'subscription'              # Assumes Subscription is related to User as 'subscription'
    )

    print(f"Found {users_to_check.count()} user(s) to check for alerts.")

    for user in users_to_check:
        print(f"\nProcessing user: {user.username}")
        
        is_subscriber = user.is_superuser
        if not is_subscriber: # Check subscription only if not superuser
            try:
                # Check if subscription attribute exists AND the subscription object itself is not None
                if hasattr(user, 'subscription') and user.subscription and user.subscription.is_active():
                    is_subscriber = True
            except Subscription.DoesNotExist: # Or Profile.DoesNotExist if subscription is on Profile
                pass # is_subscriber remains False
            except Exception as e_sub_check:
                print(f"  Error checking subscription status for {user.username}: {e_sub_check}")


        print(f"  User is_subscriber: {is_subscriber}")

        locations_to_monitor = []

       
        if hasattr(user, 'profile'):
            if is_subscriber:
                # Premium users: get all their saved locations, THEN filter by receive_notifications
                locations_to_monitor = user.profile.saved_locations.filter(receive_notifications=True).order_by('pk')[:3]
                print(f"  Subscriber: Checking {locations_to_monitor.count()} saved locations set for notifications (max 3).")
            else: # Free user
                # Free users: only check their default location IF it's set to receive notifications
                default_loc = user.profile.saved_locations.filter(is_default=True, receive_notifications=True).first()
                if default_loc:
                    locations_to_monitor = [default_loc]
                    print(f"  Free tier: Checking default location (alerts ON): {default_loc.location_name}")
                else:
                    print(f"  Free tier/Non-subscriber: User has no default location set for notifications.")


        if not locations_to_monitor:
            print(f"  No locations to monitor for {user.username}.")
            continue

        user_devices = user.webpushdevice_set.filter(active=True)
        if not user_devices.exists():
            print(f"  User {user.username} has no active push devices. Skipping.")
            continue

        nws_alerts_pushed_this_session_for_user = set()

        for loc_instance in locations_to_monitor: # Changed variable name from 'loc'
            print(f"  Checking location: {loc_instance.location_name} ({loc_instance.latitude}, {loc_instance.longitude})")
            
            zone_id = get_nws_zone_for_coords(loc_instance.latitude, loc_instance.longitude, task_user_agent)
            current_nws_alerts = fetch_alerts_by_zone_or_point(zone_id, loc_instance.latitude, loc_instance.longitude, task_user_agent)

            if not current_nws_alerts:
                print(f"    No active alerts for {loc_instance.location_name} (zone/point).")
                continue # To the next saved location for this user

            for alert in current_nws_alerts:
                nws_alert_id = alert.get('id')
                if not nws_alert_id:
                    print("    Skipping alert with no ID.")
                    continue # To the next alert

                if nws_alert_id in nws_alerts_pushed_this_session_for_user:
                    print(f"    NWS ID {nws_alert_id} (event: {alert.get('event')}) already processed for {user.username} in this run (for another of their locations).")
                    continue # To the next alert

                if NotifiedAlert.objects.filter(user=user, nws_alert_id=nws_alert_id).exists():
                    print(f"    Alert {nws_alert_id} (event: {alert.get('event')}) already notified to {user.username} previously.")
                    continue # To the next alert
                
                print(f"    NEW NWS Alert for {user.username}: {alert['event']} (for saved location: {loc_instance.location_name})")
                
                payload_dict = {
                    "head": f"{alert.get('event')} for your location: {loc_instance.location_type_label or loc_instance.location_name}",
                    "body": alert.get('headline', 'Check app for details.'),
                    "icon": "/static/images/icons/Icon_192.png", # Ensure this static path is correct
                    "url": "https://unfortunateneighbor.com/weather/",
                    "sound": "/static/sounds/danger.mp3"
                }
                json_string_payload = json.dumps(payload_dict) # Pre-serialize

                print(f"SERVER_PUSH_DEBUG: Sending payload: {json_string_payload}")
                print(f"    Attempting to send push: {json_string_payload}")

                try:
                    user_devices.send_message(json_string_payload) # Send pre-serialized JSON string
                    NotifiedAlert.objects.create(
                        user=user,
                        nws_alert_id=nws_alert_id,
                        saved_location=loc_instance # Link the specific location that triggered it
                    )
                    print(f"      Push sent and DB record created for {user.username}, NWS ID {nws_alert_id} (Location: {loc_instance.location_name})")
                    nws_alerts_pushed_this_session_for_user.add(nws_alert_id) # Mark as processed for this run
                except Exception as e:
                    print(f"    !!! FAILED to send push to {user.username} for NWS ID {nws_alert_id}: {e}")
                    traceback.print_exc()
            
        print(f"  Finished processing locations for {user.username}")

    end_time = datetime.now(timezone.utc)
    print(f"[{end_time.isoformat()}] Task finished. Duration: {end_time - start_time}")

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
