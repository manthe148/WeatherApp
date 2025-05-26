# weather/utils.py

import requests
import json
from django.conf import settings
from django.core.cache import cache
from datetime import datetime, timezone # Ensure these are imported for fromtimestamp

# Import your existing NWS helper functions from subscriptions.tasks
# These are the excellent building blocks you already have!
from subscriptions.tasks import get_nws_zone_for_coords, fetch_alerts_by_zone_or_point
# Ensure your accounts.models.SavedLocation is correctly imported if needed directly
from accounts.models import SavedLocation 

def determine_alert_priority_from_list(alerts_list):
    """
    Given a list of alert details (from fetch_alerts_by_zone_or_point),
    determines the highest priority status ('warning', 'watch', 'advisory', or None).
    """
    highest_priority_status = None
    current_priority_level = 0  # 3: Warning, 2: Watch, 1: Advisory/Statement

    if not alerts_list:
        return None

    for alert_detail in alerts_list:
        event_type = alert_detail.get('event', '').lower()

        is_warning = 'warning' in event_type
        is_watch = 'watch' in event_type
        # Consider 'statement' and 'advisory' for the lowest tier.
        # Some significant weather statements can act like advisories.
        is_advisory = 'advisory' in event_type or \
                      ('statement' in event_type and not (is_warning or is_watch))

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
    
    return highest_priority_status

def get_user_navbar_alert_info(user):
    """
    Gets the NWS alert info for the user's default location for navbar display.
    Results are cached for 10 minutes.
    Returns a dictionary: {'status': 'warning'|'watch'|'advisory'|None, 'count': int}
    """
    if not user or not user.is_authenticated:
        return {'status': None, 'count': 0}

    cache_key = f"user_navbar_alert_info_{user.id}"
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        # print(f"DEBUG NAVBAR: Returning cached alert status for user {user.id}: {cached_value}")
        return cached_value

    alert_info_to_cache = {'status': None, 'count': 0} # Default

    default_location_obj = None
    if hasattr(user, 'profile') and user.profile:
        try:
            default_location_obj = user.profile.saved_locations.filter(is_default=True, receive_notifications=True).first()
            # We only check if receive_notifications is True for their default location for the navbar indicator.
            # You can remove receive_notifications=True if you want it to show even if they don't get pushes for it.
        except Exception as e:
            print(f"NAVBAR_UTIL: Error getting default location for {user.username}: {e}")
            pass 

    if default_location_obj:
        # print(f"NAVBAR_UTIL: Checking alerts for {user.username}'s default loc: {default_location_obj.location_name}")
        
        admin_email = "your_app_contact@example.com" # Replace or get from settings
        if hasattr(settings, 'ADMIN_EMAIL_FOR_NWS_USER_AGENT'):
            admin_email = settings.ADMIN_EMAIL_FOR_NWS_USER_AGENT
        user_agent_string = f"({settings.APP_NAME_DISPLAY if hasattr(settings, 'APP_NAME_DISPLAY') else 'YourWeatherApp'}/1.0 NavbarAlertCheck; {admin_email})"


        zone_id = get_nws_zone_for_coords(
            default_location_obj.latitude, 
            default_location_obj.longitude, 
            user_agent_string
        )
        
        active_alerts_details = fetch_alerts_by_zone_or_point(
            zone_id, 
            default_location_obj.latitude, 
            default_location_obj.longitude, 
            user_agent_string
        )
        
        alert_info_to_cache['count'] = len(active_alerts_details)
        alert_info_to_cache['status'] = determine_alert_priority_from_list(active_alerts_details)
    else:
        # print(f"NAVBAR_UTIL: User {user.username} has no default location (with notifications enabled) for navbar alerts.")
        pass

    cache.set(cache_key, alert_info_to_cache, 60 * 10) # Cache for 10 minutes
    # print(f"DEBUG NAVBAR: Setting cached alert status for user {user.id}: {alert_info_to_cache}")
    return alert_info_to_cache
