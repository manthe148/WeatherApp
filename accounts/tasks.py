# /srv/radar_site_prod/accounts/tasks.py

import requests
from datetime import datetime, timezone, timedelta
import traceback
from shapely.geometry import Point, Polygon # For point-in-polygon checks

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Subquery, OuterRef
from .models import UserLocationHistory # From accounts.models

User = get_user_model()

def check_locations_against_warnings():
    """
    A Django Q task that checks the latest location of each user against active NWS
    warning polygons and updates their 'is_in_warned_area' status.
    """
    start_time = datetime.now(timezone.utc)
    print(f"[{start_time.isoformat()}] TASK_FAMILY_MAP: Running task: check_locations_against_warnings")

    # 1. Fetch all active NWS warnings with polygon geometries
    active_warning_polygons = []
    try:
        # We fetch for severe thunderstorm, tornado, and flash flood warnings. You can add more.
        # event_types = "SVR,TOR,FFW" # This would be ideal but NWS API might not filter by multiple events this way
        # For now, we fetch all active alerts and filter them.
        nws_alerts_url = "https://api.weather.gov/alerts/active?status=actual&message_type=alert"
        user_agent = getattr(settings, 'ADMIN_EMAIL_FOR_NWS_USER_AGENT', 'DjangoWeatherApp/1.0')
        headers = {'User-Agent': user_agent, 'Accept': 'application/geo+json'}

        print("TASK_FAMILY_MAP: Fetching active NWS alerts...")
        response = requests.get(nws_alerts_url, headers=headers, timeout=60)
        response.raise_for_status()
        alerts_data = response.json()

        warning_events = [
            "Tornado Warning", 
            "Severe Thunderstorm Warning", 
            "Flash Flood Warning",
            "Extreme Wind Warning"
            # Add other high-priority warning types as needed
        ]

        for alert in alerts_data.get('features', []):
            if (alert.get('geometry') and 
                alert.get('properties', {}).get('event') in warning_events):
                # NWS Polygons are often a list containing a list of coordinate pairs
                # e.g., "geometry": { "type": "Polygon", "coordinates": [[ [-95, 36], ... ]]}
                coords = alert['geometry']['coordinates'][0] 
                if len(coords) >= 4: # Need at least 4 points for a valid polygon (first and last are same)
                    active_warning_polygons.append(Polygon(coords))

        print(f"TASK_FAMILY_MAP: Found {len(active_warning_polygons)} active high-priority warning polygons.")

    except Exception as e:
        print(f"TASK_FAMILY_MAP_ERROR: Could not fetch or process NWS alert polygons: {e}")
        traceback.print_exc()
        return # Exit the task if we can't get alerts

    # 2. Get the latest location for every user who is sharing their location
    # We find the ID of the most recent history record for each user.
    latest_locations_subquery = UserLocationHistory.objects.filter(
        user=OuterRef('user')
    ).order_by('-timestamp')

    # Then we get the full objects for those latest records.
    # We only need to check locations updated in the last, say, 30 minutes.
    recent_time_filter = timezone.now() - timedelta(minutes=30)
    latest_user_locations = UserLocationHistory.objects.filter(
        pk=Subquery(latest_locations_subquery.values('pk')[:1]),
        timestamp__gte=recent_time_filter
    ).select_related('user')

    print(f"TASK_FAMILY_MAP: Found {latest_user_locations.count()} recent user location updates to check.")

    # 3. Check each location against the warning polygons
    users_in_warned_area_pks = set()
    for loc_history in latest_user_locations:
        user_point = Point(loc_history.longitude, loc_history.latitude)
        is_warned = False
        for polygon in active_warning_polygons:
            if polygon.contains(user_point):
                is_warned = True
                break # Stop checking polygons if we found one

        if is_warned:
            users_in_warned_area_pks.add(loc_history.pk)

    print(f"TASK_FAMILY_MAP: Identified {len(users_in_warned_area_pks)} location records within warned areas.")

    # 4. Update the database in bulk
    # Set is_in_warned_area to True for locations inside a polygon
    updated_true_count = UserLocationHistory.objects.filter(pk__in=users_in_warned_area_pks).update(is_in_warned_area=True)

    # Set is_in_warned_area to False for all other recent locations that were checked
    updated_false_count = UserLocationHistory.objects.filter(
        pk__in=[loc.pk for loc in latest_user_locations] # The set of locations we checked
    ).exclude(
        pk__in=users_in_warned_area_pks # Exclude those we just marked as True
    ).update(is_in_warned_area=False)

    print(f"TASK_FAMILY_MAP: Bulk update complete. Marked {updated_true_count} as warned, {updated_false_count} as not warned.")
    end_time = datetime.now(timezone.utc)
    print(f"[{end_time.isoformat()}] TASK_FAMILY_MAP: Task finished. Duration: {end_time - start_time}")
