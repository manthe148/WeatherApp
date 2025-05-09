import requests
from datetime import datetime, timezone
import traceback
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from push_notifications.models import WebPushDevice
from accounts.models import SavedLocation # Assuming SavedLocation is in accounts.models
from .models import NotifiedAlert, Subscription # Import NotifiedAlert and Subscription

User = get_user_model()

def fetch_nws_alerts_for_location(latitude, longitude):
    # User-Agent string should use the VAPID admin email for contact
    # Access it from the PUSH_NOTIFICATIONS_SETTINGS
    admin_email_claim = settings.PUSH_NOTIFICATIONS_SETTINGS.get("WP_CLAIMS", {}).get("sub", "mailto:default_admin@example.com")

    nws_api_url = f"https://api.weather.gov/alerts/active?point={latitude},{longitude}"
    headers = {
        # Corrected line:
        'User-Agent': f'MyWeatherApp/1.0 (AlertCheckerTask, {admin_email_claim})',
        'Accept': 'application/geo+json'
    }
    active_alerts_details = []
    try:
        response = requests.get(nws_api_url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        raw_alerts = data.get('features', [])
        for alert_feature in raw_alerts:
            props = alert_feature.get('properties', {})
            alert_detail = {
                'id': props.get('id'), # NWS alert ID
                'event': props.get('event', 'Weather Alert'),
                'headline': props.get('headline', 'Check weather app for details.'),
                'severity': props.get('severity'),
                'description': props.get('description', '')
            }
            if alert_detail['id']: # Only consider alerts with an ID
                active_alerts_details.append(alert_detail)
        return active_alerts_details
    except requests.exceptions.RequestException as e:
        print(f"NWS API Error for {latitude},{longitude} in task: {e}")
    except Exception as e:
        print(f"Error processing alerts for {latitude},{longitude} in task: {e}")
        traceback.print_exc()
    return []

def check_weather_alerts_and_send_pushes():
    start_time = datetime.now(timezone.utc)
    print(f"[{start_time.isoformat()}] Running task: check_weather_alerts_and_send_pushes")

    # Get users with active subscriptions and active push devices
    subscribed_users_with_devices = User.objects.filter(
        subscription__status__in=['active', 'trialing'], # Check for active Subscription
        webpushdevice__active=True # Check for active WebPushDevice
    ).distinct().prefetch_related('profile__saved_locations', 'webpushdevice_set')
    # distinct() because a user might have multiple devices

    print(f"Found {subscribed_users_with_devices.count()} users with active subscriptions and push devices.")

    for user in subscribed_users_with_devices:
        print(f"Processing user: {user.username}")
        default_location = None
        try:
            if hasattr(user, 'profile'):
                default_location = user.profile.saved_locations.filter(is_default=True).first()
            else:
                print(f"  User {user.username} has no profile.")
                continue
        except Exception as e:
            print(f"  Error getting default location for {user.username}: {e}")
            continue

        if default_location:
            print(f"  Checking alerts for default location: {default_location.location_name} ({default_location.latitude}, {default_location.longitude})")
            current_alerts = fetch_nws_alerts_for_location(
                default_location.latitude, default_location.longitude
            )

            if current_alerts:
                user_devices = user.webpushdevice_set.filter(active=True)
                if not user_devices.exists():
                    print(f"  User {user.username} has no active devices, skipping push.")
                    continue

                for alert in current_alerts:
                    nws_alert_id = alert.get('id')
                    if not nws_alert_id:
                        continue # Skip alerts without an ID

                    # Check if this alert has already been notified to this user
                    if not NotifiedAlert.objects.filter(user=user, nws_alert_id=nws_alert_id).exists():


                        print(f"  New alert for {user.username}: {alert['event']} - {alert['headline']}")

                        # --- CONSTRUCT A DELIMITED STRING PAYLOAD ---
                        alert_event_str = alert.get('event', 'Weather Alert!')
                        alert_headline_str = alert.get('headline', 'Check app for details.')
                        # Ensure these paths are root-relative for the SW
                        icon_path_str = "/static/images/icons/icon-192x192.png"
                        url_str = "/weather/" # Or a more specific URL if you have one

                        # Use a delimiter unlikely to be in the alert text itself
                        # e.g., triple pipe "|||"
                        structured_string_payload = f"{alert_event_str}|||{alert_headline_str}|||{icon_path_str}|||{url_str}"

                        print(f"  Attempting to send STRUCTURED STRING PAYLOAD: {structured_string_payload}")
                        # --- END STRUCTURED STRING PAYLOAD ---

                        try:
                            # Send the structured string
                            user_devices.send_message(structured_string_payload) 

                            NotifiedAlert.objects.create(
                                user=user,
                                nws_alert_id=nws_alert_id,
                                saved_location=default_location
                            )
                            print(f"    Push notification (structured string) sent to {user.username} for NWS ID: {nws_alert_id}")
                        except Exception as e:
                            print(f"  !!! FAILED to send push (structured string) to {user.username} for NWS ID {nws_alert_id}: {e}")
                            traceback.print_exc()
                else:
                    print(f"  Alert {nws_alert_id} already notified to {user.username}.")
            else:
                print(f"  No active alerts for {default_location.location_name}.")
        else:
            print(f"  No default location set for user: {user.username}")

    end_time = datetime.now(timezone.utc)
    print(f"[{end_time.isoformat()}] Task finished. Duration: {end_time - start_time}")
