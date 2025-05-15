# weather/grib_processing.py
import requests
import os
import pygrib
import numpy as np
import matplotlib
matplotlib.use('Agg') # Use non-interactive backend
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from datetime import datetime, timedelta, timezone
from django.conf import settings # For MEDIA_ROOT

def get_latest_gfs_rundate_and_hour(for_console_output=None):
    """Determines a recent GFS run date (YYYYMMDD) and hour string ('00', '06', '12', '18') 
       that is likely available.
    """
    now_utc = datetime.now(timezone.utc)
    # Go back about 7 hours to increase likelihood of data availability
    target_time_for_run = now_utc - timedelta(hours=7)

    run_date_str = target_time_for_run.strftime("%Y%m%d")
    hour_val = target_time_for_run.hour

    if hour_val >= 18: run_hour_str = "18"
    elif hour_val >= 12: run_hour_str = "12"
    elif hour_val >= 6: run_hour_str = "06"
    else: run_hour_str = "00"

    if for_console_output: # To avoid printing when called from other functions silently
        for_console_output(f"Current UTC for GFS run selection: {now_utc.strftime('%Y-%m-%d %H:%M:%SZ')}")
        for_console_output(f"Targeting GFS run: Date={run_date_str}, Hour={run_hour_str}Z")
    return run_date_str, run_hour_str

def generate_gfs_plot_for_hour(run_date_str, model_run_hour_str, forecast_hour_str, for_console_output=None):
    """
    Generates a GFS 2m Temperature plot for a specific run and forecast hour.
    Returns True if successful, False otherwise.
    'for_console_output' is a function like self.stdout.write or print.
    """
    if for_console_output is None:
        for_console_output = print # Default to print if no output func provided

    parameter_name_grib = "2 metre temperature"
    # Ensure forecast_hour_str is correctly formatted (3 digits, zero-padded)
    try:
        fhr_int = int(forecast_hour_str)
        forecast_hour_str = f"{fhr_int:03d}"
    except ValueError:
        for_console_output(f"Error: Invalid forecast_hour_str '{forecast_hour_str}'. Must be convertible to int.")
        return False, None

    gfs_url = f"https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/gfs.{run_date_str}/{model_run_hour_str}/atmos/gfs.t{model_run_hour_str}z.pgrb2.0p25.f{forecast_hour_str}"

    # Use a temporary filename based on all varying parts to avoid clashes if run in parallel
    grib_filename_temp = f"gfs_temp_data_{run_date_str}_{model_run_hour_str}_{forecast_hour_str}.grb2"
    output_image_name = f"gfs_t2m_{run_date_str}_{model_run_hour_str}z_f{forecast_hour_str}.png"
    output_image_full_path = os.path.join(settings.MEDIA_ROOT, 'model_plots', output_image_name)

    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_image_full_path), exist_ok=True)

    # Optional: Check if file already exists and is recent (e.g., from this run)
    # For now, let's always regenerate if called, or command/task can decide.
    # if os.path.exists(output_image_full_path):
    #     for_console_output(f"Image {output_image_name} already exists. Skipping generation.")
    #     return True, output_image_full_path # Assuming success if it exists

    for_console_output(f"  Attempting GFS F{forecast_hour_str}: Downloading from {gfs_url}")
    try:
        response = requests.get(gfs_url, stream=True, timeout=180) # Longer timeout for potentially large files
        response.raise_for_status()
        with open(grib_filename_temp, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        for_console_output(f"    Downloaded to {grib_filename_temp}")
    except requests.exceptions.RequestException as e:
        for_console_output(f"    Error downloading GRIB file for F{forecast_hour_str}: {e}")
        if os.path.exists(grib_filename_temp): os.remove(grib_filename_temp)
        return False, None
    except Exception as e:
        for_console_output(f"    Unexpected error during download for F{forecast_hour_str}: {e}")
        if os.path.exists(grib_filename_temp): os.remove(grib_filename_temp)
        return False, None

    try:
        for_console_output(f"    Processing GRIB file: {grib_filename_temp}")
        grbs = pygrib.open(grib_filename_temp)
        temp_grib_message = next((grb for grb in grbs if parameter_name_grib.lower() in grb.name.lower() and grb.level == 2 and grb.typeOfLevel == 'heightAboveGround'), None)

        if not temp_grib_message:
            for_console_output(f"    Could not find '{parameter_name_grib}' at 2m in GRIB for F{forecast_hour_str}.")
            return False, None # pygrib automatically closes file on 'del grbs' or exit

        data_values = temp_grib_message.values
        lats, lons = temp_grib_message.latlons()
        data_values_f = (data_values - 273.15) * 9/5 + 32
        grbs.close()
        for_console_output(f"    GRIB data processed for F{forecast_hour_str}.")

        for_console_output(f"    Generating plot for F{forecast_hour_str}...")
        fig = plt.figure(figsize=(12, 9))
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_extent([-125, -65, 23, 50], crs=ccrs.PlateCarree())
        ax.add_feature(cfeature.COASTLINE)
        ax.add_feature(cfeature.BORDERS, linestyle=':')
        ax.add_feature(cfeature.STATES, linestyle=':')
        levels = np.arange(0, 105, 5)
