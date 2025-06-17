# /srv/radar_site_prod/subscriptions/tasks.py

import requests
from datetime import datetime, timezone, timedelta
import traceback
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q, Subquery, OuterRef
from django.urls import reverse
from push_notifications.models import WebPushDevice
from shapely.geometry import Point, Polygon

# Adjust these imports based on where your models live
from accounts.models import SavedLocation, Profile, Family, UserLocationHistory
from .models import NotifiedAlert, Subscription

User = get_user_model()


# --- Helper Functions ---
# These must be defined before they are called by the main task below.

def get_nws_zone_for_coords(latitude, longitude, user_agent):
    """Helper to get the NWS forecast zone for given coordinates."""
    nws_points_url = f"https://api.weather.gov/points/{latitude},{longitude}"
    nws_headers = {'User-Agent': user_agent, 'Accept': 'application/geo+json'}
    try:
        points_response = requests.get(nws_points_url, headers=nws_headers, timeout=15)
        points_response.raise_for_status()
        points_data = points_response.json()
        zone_url = points_data.get('properties', {}).get('forecastZone')
        if zone_url:
            return zone_url.split('/')[-1]
    except Exception as e:
        print(f"HELPER_ERROR: Could not get NWS zone for ({latitude},{longitude}): {e}")
    return None

def fetch_alerts_by_point(latitude, longitude, task_user_agent):
    """Fetches alerts by point from the NWS API."""
    active_alerts_details = []
    nws_headers = {'User-Agent': task_user_agent, 'Accept': 'application/geo+json'}
    url = f"https://api.weather.gov/alerts/active?point={latitude},{longitude}"
    
    try:
        response = requests.get(url, headers=nws_headers, timeout=30)
        response.raise_for_status()
        for alert_feature in response.json().get('features', []):
            props = alert_feature.get('properties', {})
            if props.get('id'): # Only process alerts with an ID
                active_alerts_details.append({
                    'id': props.get('id'),
                    'event': props.get('event', 'Weather Alert'),
                    'headline': props.get('headline', 'Check app for details.'),
                })
    except Exception as e:
        print(f"HELPER_ERROR: NWS Alerts API Error for ({latitude},{longitude}): {e}")
    return active_alerts_details

def fetch_active_alerts_with_polygons(task_user_agent):
    """Fetches all active, high-priority NWS warning polygons once."""
    active_warnings = []
    try:
        nws_alerts_url = "https://api.weather.gov/alerts/active?status=actual&message_type=alert"
        headers = {'User-Agent': task_user_agent, 'Accept': 'application/geo+json'}
        response = requests.get(nws_alerts_url, headers=headers, timeout=60)
        response.raise_for_status()
        warning_events = ["Tornado Warning", "Severe Thunderstorm Warning", "Flash Flood Warning", "Extreme Wind Warning"]
        for alert in response.json().get('features', []):
            properties = alert.get('properties', {})
            if (alert.get('geometry') and alert['geometry']['type'] == 'Polygon' and properties.get('event') in warning_events):
                coords = alert['geometry']['coordinates'][0]
                if len(coords) >= 4:
                    active_warnings.append({
                        "polygon": Polygon(coords),
                        "event": properties.get('event')
                    })
    except Exception as e:
        print(f"HELPER_ERROR: Could not fetch NWS alert polygons: {e}")
    return active_warnings


# --- THE UNIFIED ALERTING TASK ---
def process_all_alerts():
    """A single, unified task for all NWS alert notifications."""
    start_time = datetime.now(timezone.utc)
    print(f"[{start_time.isoformat()}] --- TASK START: process_all_alerts ---")
    task_user_agent = f"UnfortunateNeighborWeather/1.0 (AlertCheckerTask; {settings.DEFAULT_FROM_EMAIL})"

    # --- Part 1: Personal Alerts for Saved Locations ---
    users_to_check = User.objects.filter(webpushdevice__active=True).distinct().prefetch_related('profile__saved_locations', 'webpushdevice_set')
    print(f"Saved Locations: Found {users_to_check.count()} user(s) to check.")
    for user in users_to_check:
        if not hasattr(user, 'profile'): continue

        pushed_event_types_this_run = set()
        already_notified_ids = set(NotifiedAlert.objects.filter(user=user).values_list('nws_alert_id', flat=True))

        locations_to_monitor = user.profile.saved_locations.filter(receive_notifications=True)
        if not user.profile.has_premium_access:
            locations_to_monitor = locations_to_monitor.filter(is_default=True)
        
        if not locations_to_monitor.exists(): continue

        for loc_instance in locations_to_monitor:
            point_alerts = fetch_alerts_by_point(loc_instance.latitude, loc_instance.longitude, task_user_agent)
            for alert in point_alerts:
                nws_alert_id = alert.get('id')
                event_name = alert.get('event')
                if not (nws_alert_id and event_name): continue

                if nws_alert_id in already_notified_ids or event_name in pushed_event_types_this_run: continue
                
                print(f"  -> NEW Personal Alert '{event_name}' for {user.username}")
                base_url = settings.SITE_DOMAIN.rstrip('/')
                payload = json.dumps({
                    "head": f"{event_name} for {loc_instance.location_name}", "body": alert.get('headline'),
                    "icon": f"{base_url}{settings.STATIC_URL}images/icons/Icon_192.png", "url": f"{base_url}{reverse('weather:weather_page')}"
                })
                try:
                    user.webpushdevice_set.filter(active=True).send_message(payload)
                    NotifiedAlert.objects.create(user=user, nws_alert_id=nws_alert_id, saved_location=loc_instance)
                    pushed_event_types_this_run.add(event_name)
                    print(f"    -> SUCCESS: Sent PERSONAL alert to {user.username}.")
                except Exception as e:
                    print(f"    -> FAILED to send personal alert to {user.username}: {e}")

    # --- Part 2: Family Member Shared Location Alerts ---
    print("\nFamily Map: Starting check for family member locations.")
    active_warnings = fetch_active_alerts_with_polygons(task_user_agent)
    if not active_warnings:
        print("Family Map: No active warning polygons found. Skipping family check.")
    else:
        latest_locations_subquery = UserLocationHistory.objects.filter(user=OuterRef('user')).order_by('-timestamp')
        recent_time_filter = datetime.now(timezone.utc) - timedelta(minutes=30)
        latest_user_locations = UserLocationHistory.objects.filter(pk=Subquery(latest_locations_subquery.values('pk')[:1]), timestamp__gte=recent_time_filter).select_related('user')

        print(f"Family Map: Found {latest_user_locations.count()} recent user location pings to check.")
        pks_in_warned_area = set()
        for loc_history in latest_user_locations:
            user_point = Point(loc_history.longitude, loc_history.latitude)
            for warning in active_warnings:
                if warning["polygon"].contains(user_point):
                    pks_in_warned_area.add(loc_history.pk)
                    warned_user = loc_history.user
                    family_to_notify = Family.objects.filter(Q(owner=warned_user) | Q(members=warned_user)).first()
                    if family_to_notify:
                        all_family_members = list(set([family_to_notify.owner] + list(family_to_notify.members.all())))
                        for member_to_notify in all_family_members:
                            if member_to_notify.id == warned_user.id: continue
                            devices_to_notify = member_to_notify.webpushdevice_set.filter(active=True)
                            if devices_to_notify.exists():
                                base_url = settings.SITE_DOMAIN.rstrip('/')
                                payload = json.dumps({
                                    "head": f"Family Alert: {warned_user.username} in a {warning['event']}!",
                                    "body": "Their reported location is within an active warned area.",
                                    "icon": f"{base_url}{settings.STATIC_URL}images/icons/Icon_192_alert.png",
                                    "url": f"{base_url}{reverse('accounts:family_map')}",
                                    "tag": f"family-alert-{warned_user.id}"
                                })
                                try:
                                    devices_to_notify.send_message(payload)
                                    print(f"    -> SUCCESS: Sent FAMILY alert about {warned_user.username} to {member_to_notify.username}.")
                                except Exception as e:
                                    print(f"    -> FAILED to send family alert to {member_to_notify.username}: {e}")
                    break
        UserLocationHistory.objects.filter(pk__in=pks_in_warned_area).update(is_in_warned_area=True)
        pks_checked = {loc.pk for loc in latest_user_locations}
        UserLocationHistory.objects.filter(pk__in=(pks_checked - pks_in_warned_area)).update(is_in_warned_area=False)

    end_time = datetime.now(timezone.utc)
    print(f"[{end_time.isoformat()}] --- UNIFIED ALERT TASK FINISHED. Duration: {end_time - start_time} ---")
