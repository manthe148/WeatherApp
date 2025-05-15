from django.apps import AppConfig
from django.utils import timezone # For setting next_run
from datetime import timedelta    # For setting next_run

class WeatherConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'weather'

    def ready(self):
        # Import here to avoid AppRegistryNotReady errors
        from django_q.tasks import schedule, Schedule
        from django.conf import settings

        if not settings.configured: # Ensure settings are configured
            return

        # Only schedule if Q_CLUSTER is configured, otherwise it might fail if DB isn't ready
        # or if it's a manage.py command that doesn't need Q (like makemigrations)
        if hasattr(settings, 'Q_CLUSTER'):
            task_path = 'weather.tasks.automated_gfs_plot_generation'
            schedule_name = 'Generate GFS Model Plots'
            desired_interval_hours = 3 # Run every 3 hours

            try:
                schedule_obj = Schedule.objects.get(name=schedule_name)
                if schedule_obj.minutes != (desired_interval_hours * 60) or \
                   schedule_obj.schedule_type != Schedule.HOURLY or \
                   schedule_obj.func != task_path:

                    schedule_obj.func = task_path
                    schedule_obj.minutes = None # Clear minutes if using hours
                    schedule_obj.hours = desired_interval_hours
                    schedule_obj.schedule_type = Schedule.HOURLY
                    schedule_obj.repeats = -1
                    schedule_obj.next_run = timezone.now() + timedelta(hours=desired_interval_hours)
                    schedule_obj.save()
                    print(f"UPDATED task '{schedule_name}' to run every {desired_interval_hours} hour(s).")
                else:
                    print(f"Task '{schedule_name}' already scheduled correctly for every {desired_interval_hours} hour(s).")
            except Schedule.DoesNotExist:
                schedule(
                    task_path,
                    name=schedule_name,
                    schedule_type=Schedule.HOURLY, # Use HOURS type
                    hours=desired_interval_hours,    # Run every 3 hours
                    repeats=-1,          # Repeat indefinitely
                    next_run=timezone.now() + timedelta(minutes=5) # Start in 5 mins for first run
                )
                print(f"Scheduled task '{schedule_name}' to run every {desired_interval_hours} hour(s).")
            except Exception as e:
                print(f"Could not schedule GFS plot task '{schedule_name}': {e}")
                print("This might occur if django_q tables are not yet migrated or DB is not ready.")
        else:
            print("Django Q_CLUSTER not configured in settings. Skipping GFS plot task scheduling.")
