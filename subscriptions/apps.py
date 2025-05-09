# subscriptions/apps.py
from django.apps import AppConfig
# Add these imports if they are not already at the top of your apps.py
from django.utils import timezone # For setting next_run
from datetime import timedelta    # For setting next_run

class SubscriptionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'subscriptions'

    def ready(self):
        # --- Schedule the push notification task ---
        # Make sure these imports are within ready() or at file top
        from django_q.tasks import schedule, Schedule # Import Schedule model
        # from django_q.models import Schedule # Redundant if imported above

        task_path = 'subscriptions.tasks.check_weather_alerts_and_send_pushes'
        schedule_name = 'Check Weather Alerts & Send Pushes'
        desired_interval_minutes = 10 # Set desired interval

        try:
            # Try to get the existing schedule
            schedule_obj = Schedule.objects.get(name=schedule_name)
            # Check if the interval needs updating
            if schedule_obj.minutes != desired_interval_minutes or schedule_obj.schedule_type != Schedule.MINUTES:
                schedule_obj.minutes = desired_interval_minutes
                schedule_obj.schedule_type = Schedule.MINUTES
                schedule_obj.repeats = -1 # Ensure it repeats indefinitely
                schedule_obj.next_run = timezone.now() + timedelta(minutes=desired_interval_minutes) # Schedule next run
                schedule_obj.save()
                print(f"UPDATED task '{schedule_name}' to run every {desired_interval_minutes} minute(s).")
            else:
                print(f"Task '{schedule_name}' already scheduled correctly for every {desired_interval_minutes} minute(s).")
        except Schedule.DoesNotExist:
            # If schedule doesn't exist, create it
            schedule(
                task_path,
                name=schedule_name,
                schedule_type=Schedule.MINUTES,
                minutes=desired_interval_minutes,
                repeats=-1,  # Repeat indefinitely
                next_run=timezone.now() + timedelta(minutes=desired_interval_minutes) # Schedule first run
            )
            print(f"Scheduled task '{schedule_name}' to run every {desired_interval_minutes} minute(s).")
        except Exception as e:
            # Catch other potential errors during scheduling (e.g., if DB isn't ready during initial startup)
            print(f"Could not schedule task '{schedule_name}' due to an error: {e}")
            print("This might happen during initial migrations if the django_q tables don't exist yet.")
            print("If this is not the first run, check your database and django_q setup.")

        # --- End Task Scheduling ---
