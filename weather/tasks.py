# weather/tasks.py
from weather.grib_processing import get_latest_gfs_rundate_and_hour, generate_gfs_plot_for_hour
from django_q.tasks import schedule, Schedule # For potential re-scheduling or checking
from datetime import datetime, timezone, timedelta
import os
from django.conf import settings


def automated_gfs_plot_generation():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Task: automated_gfs_plot_generation starting...")

    run_date_str, model_run_hour_str = get_latest_gfs_rundate_and_hour(print) # Use print for task logging

    # Define which forecast hours to generate
    # Example: 0, 3, 6, 9, 12, 18, 24, 36, 48, 72, 96, 120 hours
    forecast_hours_to_generate = [f"{h:03d}" for h in range(0, 121, 6)] # Every 6 hours up to 120
    # forecast_hours_to_generate.extend([f"{h:03d}" for h in range(0, 25, 3)]) # Example for more frequent early hours
    # forecast_hours_to_generate = sorted(list(set(forecast_hours_to_generate))) # Ensure uniqueness and order

    print(f"  Target GFS Run: {run_date_str} {model_run_hour_str}Z")
    print(f"  Will attempt to generate plots for FHRs: {forecast_hours_to_generate}")

    generated_count = 0
    failed_count = 0

    for fhr_str in forecast_hours_to_generate:
        # Optional: Check if image already exists and is for the CURRENT run cycle.
        # This prevents re-generating if the task runs multiple times for the same GFS cycle.
        output_image_name_check = f"gfs_t2m_{run_date_str}_{model_run_hour_str}z_f{fhr_str}.png"
        output_image_full_path_check = os.path.join(settings.MEDIA_ROOT, 'model_plots', output_image_name_check)

        if os.path.exists(output_image_full_path_check):
            print(f"    Plot for F{fhr_str} (Run: {run_date_str} {model_run_hour_str}Z) already exists. Skipping.")
            generated_count +=1 # Count it as "available"
            continue

        print(f"  Generating plot for F{fhr_str}...")
        success, _ = generate_gfs_plot_for_hour(
            run_date_str,
            model_run_hour_str,
            fhr_str,
            print # Pass print for logging within the function
        )
        if success:
            generated_count += 1
        else:
            failed_count += 1

    print(f"[{datetime.now(timezone.utc).isoformat()}] Task: automated_gfs_plot_generation finished. Generated: {generated_count}, Failed: {failed_count} for run {run_date_str} {model_run_hour_str}Z.")
