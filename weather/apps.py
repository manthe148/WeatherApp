# weather/apps.py
from django.apps import AppConfig
from django.utils import timezone 
from datetime import timedelta    

class WeatherConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'weather'

    def ready(self):
        from django_q.tasks import schedule, Schedule
        from django.conf import settings
        import traceback # For more detailed error logging if needed

        print("WeatherConfig.ready() called - attempting to schedule tasks.")

        if not settings.configured:
            print("WeatherConfig.ready(): Settings not configured yet. Skipping task scheduling.")
            return

        if hasattr(settings, 'Q_CLUSTER'):
            print("WeatherConfig.ready(): Q_CLUSTER found, proceeding with scheduling.")

            # --- GFS Plot Generation Task ---
            gfs_task_path = 'weather.tasks.automated_gfs_plot_generation'
            gfs_schedule_name = 'Generate GFS Model Plots'
            gfs_desired_interval_hours = 3 
            gfs_interval_minutes = gfs_desired_interval_hours * 60 # Interval in minutes

            try:
                print(f"  Attempting to get/update schedule for GFS task: '{gfs_schedule_name}'")
                gfs_schedule_obj = Schedule.objects.get(name=gfs_schedule_name)
                print(f"    Found existing GFS schedule.")

                # Check if update is needed
                if (gfs_schedule_obj.minutes != gfs_interval_minutes or
                    gfs_schedule_obj.schedule_type != Schedule.HOURLY or 
                    gfs_schedule_obj.func != gfs_task_path):

                    print(f"    Updating GFS schedule '{gfs_schedule_name}'...")
                    gfs_schedule_obj.func = gfs_task_path
                    gfs_schedule_obj.minutes = gfs_interval_minutes # Use minutes for HOURLY type
                    gfs_schedule_obj.schedule_type = Schedule.HOURLY
                    gfs_schedule_obj.repeats = -1
                    gfs_schedule_obj.next_run = timezone.now() + timedelta(minutes=gfs_interval_minutes) 
                    gfs_schedule_obj.save()
                    print(f"    SUCCESS: UPDATED GFS task '{gfs_schedule_name}' to run every {gfs_desired_interval_hours} hour(s) (as {gfs_interval_minutes} minutes).")
                else:
                    print(f"    GFS Task '{gfs_schedule_name}' already scheduled correctly.")
            except Schedule.DoesNotExist:
                print(f"  GFS schedule '{gfs_schedule_name}' does not exist. Creating new schedule.")
                schedule(
                    gfs_task_path, 
                    name=gfs_schedule_name, 
                    schedule_type=Schedule.HOURLY,
                    minutes=gfs_interval_minutes, # Use minutes for HOURLY type
                    repeats=-1,
                    next_run=timezone.now() + timedelta(minutes=5) # Initial run in 5 mins
                )
                print(f"    SUCCESS: Scheduled new GFS task '{gfs_schedule_name}' to run every {gfs_desired_interval_hours} hour(s) (as {gfs_interval_minutes} minutes).")
            except Exception as e:
                print(f"    ERROR: Could not schedule or update GFS plot task '{gfs_schedule_name}': {e}")
                # print(traceback.format_exc()) # Uncomment for full traceback during debug

            # --- NAM Plot Generation Task ---
            print(f"\n  Attempting to schedule/update NAM task...")
            nam_task_path = 'weather.tasks.automated_nam_plot_generation'
            nam_schedule_name = 'Generate NAM Model Plots'
            nam_desired_interval_hours = 3 
            nam_interval_minutes = nam_desired_interval_hours * 60

            try:
                print(f"  NAM Task: Trying to get schedule named '{nam_schedule_name}'")
                nam_schedule_obj = Schedule.objects.get(name=nam_schedule_name)
                print(f"    Found existing NAM schedule.")

                update_needed = False
                if nam_schedule_obj.func != nam_task_path: update_needed = True
                if nam_schedule_obj.schedule_type != Schedule.HOURLY: update_needed = True
                if nam_schedule_obj.minutes != nam_interval_minutes: update_needed = True

                if update_needed:
                    print(f"    NAM Task: Updating schedule for '{nam_schedule_name}'...")
                    nam_schedule_obj.func = nam_task_path
                    nam_schedule_obj.minutes = nam_interval_minutes 
                    nam_schedule_obj.schedule_type = Schedule.HOURLY
                    nam_schedule_obj.repeats = -1
                    nam_schedule_obj.next_run = timezone.now() + timedelta(minutes=nam_interval_minutes, seconds=30) # Stagger
                    nam_schedule_obj.save()
                    print(f"    SUCCESS: UPDATED NAM task '{nam_schedule_name}' to run every {nam_desired_interval_hours} hour(s) (as {nam_interval_minutes} minutes).")
                else:
                    print(f"    NAM Task '{nam_schedule_name}' already scheduled correctly.")
            except Schedule.DoesNotExist:
                print(f"  NAM schedule '{nam_schedule_name}' does not exist. Creating new schedule.")
                schedule(
                    nam_task_path, 
                    name=nam_schedule_name, 
                    schedule_type=Schedule.HOURLY, 
                    minutes=nam_interval_minutes,    
                    repeats=-1,
                    next_run=timezone.now() + timedelta(minutes=1) # Initial run in 10 mins
                )
                print(f"    SUCCESS: Scheduled new NAM task '{nam_schedule_name}' to run every {nam_desired_interval_hours} hour(s) (as {nam_interval_minutes} minutes).")
            except Exception as e:
                print(f"    ERROR: Could not schedule or update NAM plot task '{nam_schedule_name}': {e}")
                # print(traceback.format_exc()) # Uncomment for full traceback during debug
        else:
            print("WeatherConfig.ready(): Django Q_CLUSTER not configured in settings. Skipping model plot task scheduling.")
