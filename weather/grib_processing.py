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
import traceback




def get_gfs_image_details_with_fallback(requested_fhr_str, for_console_output=None):
    """
    Tries to find the GFS plot image for the requested forecast hour (fhr).
    1. Checks the latest expected GFS run.
    2. If not found, checks the GFS run before that.
    Returns a dictionary with:
    'image_exists': bool, 
    'image_url': str or None,
    'display_message': str (e.g., "Showing F006 for 20250515 06Z run")
    'actual_run_date': str, 
    'actual_run_hour': str, 
    'actual_fhr': str
    """
    if for_console_output is None:
        for_console_output = print

    # Validate and format requested_fhr_str
    try:
        fhr_int = int(requested_fhr_str)
        fhr_to_check = f"{fhr_int:03d}"
    except ValueError:
        for_console_output(f"Warning: Invalid requested_fhr '{requested_fhr_str}', defaulting to '006'.")
        fhr_to_check = "006"

    # --- Attempt 1: Latest Expected Run ---
    now_utc = datetime.now(timezone.utc)
    # Target a run that should be available (e.g., ~7 hours old)
    latest_expected_run_time = now_utc - timedelta(hours=7) 

    def get_run_cycle(dt_object):
        run_date = dt_object.strftime("%Y%m%d")
        hour_val = dt_object.hour
        if hour_val >= 18: run_h_str = "18"
        elif hour_val >= 12: run_h_str = "12"
        elif hour_val >= 6: run_h_str = "06"
        else: run_h_str = "00"
        return run_date, run_h_str

    run_date_str, model_run_hour_str = get_run_cycle(latest_expected_run_time)
    for_console_output(f"  Attempting latest run: {run_date_str} {model_run_hour_str}Z for F{fhr_to_check}")

    expected_image_filename = f"gfs_t2m_{run_date_str}_{model_run_hour_str}z_f{fhr_to_check}.png"
    expected_image_media_path = os.path.join('model_plots', expected_image_filename)
    full_image_filesystem_path = os.path.join(settings.MEDIA_ROOT, expected_image_media_path)

    if os.path.exists(full_image_filesystem_path):
        image_url = settings.MEDIA_URL + expected_image_media_path
        display_message = f"Showing GFS 2m Temp - F{fhr_to_check} (Run: {run_date_str} {model_run_hour_str}Z)"
        for_console_output(f"    Found latest image: {image_url}")
        return {
            'image_exists': True, 'image_url': image_url, 'display_message': display_message,
            'actual_run_date': run_date_str, 'actual_run_hour': model_run_hour_str, 'actual_fhr': fhr_to_check
        }

    for_console_output(f"    Latest image not found ({expected_image_filename}). Trying previous run.")

    # --- Attempt 2: Previous Run (6 hours before the 'latest_expected_run_time's cycle) ---
    # To get the previous cycle, subtract 6 hours from the *start* of the latest_expected_run_time's cycle
    latest_run_start_dt = datetime(
        latest_expected_run_time.year, latest_expected_run_time.month, latest_expected_run_time.day,
        int(model_run_hour_str), 0, 0, tzinfo=timezone.utc
    )
    previous_expected_run_time = latest_run_start_dt - timedelta(hours=6)
    prev_run_date_str, prev_model_run_hour_str = get_run_cycle(previous_expected_run_time)

    for_console_output(f"  Attempting previous run: {prev_run_date_str} {prev_model_run_hour_str}Z for F{fhr_to_check}")

    expected_image_filename_prev = f"gfs_t2m_{prev_run_date_str}_{prev_model_run_hour_str}z_f{fhr_to_check}.png"
    expected_image_media_path_prev = os.path.join('model_plots', expected_image_filename_prev)
    full_image_filesystem_path_prev = os.path.join(settings.MEDIA_ROOT, expected_image_media_path_prev)

    if os.path.exists(full_image_filesystem_path_prev):
        image_url = settings.MEDIA_URL + expected_image_media_path_prev
        display_message = f"Showing GFS 2m Temp - F{fhr_to_check} (Previous Run: {prev_run_date_str} {prev_model_run_hour_str}Z - Latest not yet available)"
        for_console_output(f"    Found previous run image: {image_url}")
        return {
            'image_exists': True, 'image_url': image_url, 'display_message': display_message,
            'actual_run_date': prev_run_date_str, 'actual_run_hour': prev_model_run_hour_str, 'actual_fhr': fhr_to_check
        }

    for_console_output(f"    Previous run image also not found ({expected_image_filename_prev}).")
    display_message = f"GFS 2m Temp - F{fhr_to_check} (Run: {run_date_str} {model_run_hour_str}Z) is not available. Previous run also not found."
    return {
        'image_exists': False, 'image_url': None, 'display_message': display_message,
        'actual_run_date': run_date_str, 'actual_run_hour': model_run_hour_str, 'actual_fhr': fhr_to_check # Still report what was targeted
    }

def get_latest_gfs_rundate_and_hour(for_console_output=None):
    """Determines a recent GFS run date (YYYYMMDD) and hour string ('00', '06', '12', '18') 
       that is likely available.
    """
    if for_console_output is None:
        for_console_output = print 

    now_utc = datetime.now(timezone.utc)
    target_time_for_run = now_utc - timedelta(hours=7)

    run_date_str = target_time_for_run.strftime("%Y%m%d")
    hour_val = target_time_for_run.hour

    if hour_val >= 18: run_hour_str = "18"
    elif hour_val >= 12: run_hour_str = "12"
    elif hour_val >= 6: run_hour_str = "06"
    else: run_hour_str = "00"

    for_console_output(f"Current UTC for GFS run selection: {now_utc.strftime('%Y-%m-%d %H:%M:%SZ')}")
    for_console_output(f"Targeting GFS run: Date={run_date_str}, Hour={run_hour_str}Z")
    return run_date_str, run_hour_str


# weather/grib_processing.py
# Ensure all necessary imports are at the top:
# requests, os, pygrib, numpy, matplotlib, plt, ccrs, cfeature, datetime, timedelta, timezone, settings, traceback

# Keep get_latest_gfs_rundate_and_hour function as is

def generate_gfs_plot_for_hour(run_date_str, model_run_hour_str, forecast_hour_str_arg, for_console_output=None): # Renamed arg for clarity
    if for_console_output is None:
        for_console_output = print

    parameter_name_grib = "2 metre temperature" # Used for human-readable part of message
    param_short_name_select = '2t' # Used for pygrib.select()

    try:
        fhr_int = int(forecast_hour_str_arg)
        forecast_hour_str_fmt = f"{fhr_int:03d}" # This is the formatted FHR for URLs and filenames
    except ValueError:
        for_console_output(f"    Error: Invalid forecast_hour_str_arg '{forecast_hour_str_arg}'. Not parsable.")
        return False, None

    # --- DEBUG: Print values used for filename and URL ---
    for_console_output(f"    DEBUG fn_generate: Received FHR_ARG='{forecast_hour_str_arg}', Formatted FHR_FMT='{forecast_hour_str_fmt}'")
    # --- END DEBUG ---

    gfs_url = f"https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/gfs.{run_date_str}/{model_run_hour_str}/atmos/gfs.t{model_run_hour_str}z.pgrb2.0p25.f{forecast_hour_str_fmt}"
    
    # THIS IS WHERE THE FILENAME IS CONSTRUCTED
    grib_filename_temp = f"gfs_temp_data_{run_date_str}_{model_run_hour_str}_{forecast_hour_str_fmt}.grb2"
    output_image_name = f"gfs_t2m_{run_date_str}_{model_run_hour_str}z_f{forecast_hour_str_fmt}.png"
    output_image_full_path = os.path.join(settings.MEDIA_ROOT, 'model_plots', output_image_name)
    
    # --- DEBUG: Print constructed filenames ---
    for_console_output(f"    DEBUG fn_generate: Constructed grib_filename_temp: {grib_filename_temp}")
    for_console_output(f"    DEBUG fn_generate: Constructed output_image_name: {output_image_name}")
    # --- END DEBUG ---
    
    os.makedirs(os.path.dirname(output_image_full_path), exist_ok=True)

    # Optional: Check if final plot image already exists
    if os.path.exists(output_image_full_path):
        for_console_output(f"    Plot image {output_image_name} already exists. Skipping generation for F{forecast_hour_str_fmt}.")
        return True, output_image_full_path

    for_console_output(f"  Attempting GFS F{forecast_hour_str_fmt} for run {run_date_str}/{model_run_hour_str}Z: Downloading from {gfs_url}")
    try:
        response = requests.get(gfs_url, stream=True, timeout=180)
        response.raise_for_status()
        with open(grib_filename_temp, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        for_console_output(f"    Downloaded to {grib_filename_temp}")
    except requests.exceptions.RequestException as e:
        for_console_output(f"    Error downloading GRIB file for F{forecast_hour_str_fmt}: {e}")
        if os.path.exists(grib_filename_temp): os.remove(grib_filename_temp)
        return False, None
    except Exception as e:
        for_console_output(f"    Unexpected error during download for F{forecast_hour_str_fmt}: {e}")
        if os.path.exists(grib_filename_temp): os.remove(grib_filename_temp)
        return False, None

    try:
        for_console_output(f"    Processing GRIB file: {grib_filename_temp}")
        grbs = pygrib.open(grib_filename_temp)
        
        # --- For debugging GRIB contents if 'select' fails ---
        for_console_output(f"    --- GRIB Messages in {grib_filename_temp} (for F{forecast_hour_str_fmt}) ---")
        messages_found_count = 0
        for i, msg_debug in enumerate(grbs): # Use a different variable name for the debug loop
            messages_found_count += 1
            print_msg = (f"    Msg {i+1}: Name='{msg_debug.name}', "
                         f"Level={msg_debug.level}, TypeOfLevel='{msg_debug.typeOfLevel}', "
                         f"shortName='{msg_debug.shortName if hasattr(msg_debug, 'shortName') else 'N/A'}'")
            for_console_output(print_msg) # Use for_console_output
            if messages_found_count >= 20: # Print first 20 messages for brevity
                for_console_output("    ... (and possibly more messages, stopping debug list at 20)")
                break 
        grbs.seek(0) # IMPORTANT: Rewind GRIB file for further processing by grbs.select()
        for_console_output(f"    --- End GRIB Message Debug List (found {messages_found_count} total if <20) ---")
        # --- End Debug GRIB Contents ---

        selected_messages = grbs.select(shortName=param_short_name_select, level=2, typeOfLevel='heightAboveGround')
        
        temp_grib_message = None
        if selected_messages:
            temp_grib_message = selected_messages[0]
            for_console_output(f"    Found GRIB message via select: {temp_grib_message.name} (level {temp_grib_message.level} {temp_grib_message.typeOfLevel})")
        
        if not temp_grib_message:
            for_console_output(f"    Could not find '{parameter_name_grib}' (shortName '{param_short_name_select}', level 2, typeOfLevel 'heightAboveGround') in GRIB for F{forecast_hour_str_fmt}.")
            grbs.close() 
            return False, None

        data_values = temp_grib_message.values
        lats, lons = temp_grib_message.latlons()
        data_values_f = (data_values - 273.15) * 9/5 + 32
        grbs.close()
        for_console_output(f"    GRIB data processed for F{forecast_hour_str_fmt}.")

        for_console_output(f"    Generating plot for F{forecast_hour_str_fmt}...")
        fig = plt.figure(figsize=(12, 9))
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_extent([-125, -65, 23, 50], crs=ccrs.PlateCarree())
        ax.add_feature(cfeature.COASTLINE)
        ax.add_feature(cfeature.BORDERS, linestyle=':')
        ax.add_feature(cfeature.STATES, linestyle=':')
        levels = np.arange(0, 105, 5)
        contour = plt.contourf(lons, lats, data_values_f, levels=levels, transform=ccrs.PlateCarree(), cmap='jet', extend='both')
        plt.colorbar(contour, ax=ax, orientation='horizontal', label='Temperature (°F)', pad=0.05, shrink=0.7)
        ax.set_title(f'GFS 2m Temperature Forecast (°F)\nRun: {run_date_str} {model_run_hour_str}Z - Forecast: F{forecast_hour_str_fmt}')
        
        plt.savefig(output_image_full_path, bbox_inches='tight', pad_inches=0.1)
        plt.close(fig)
        for_console_output(f"    SUCCESS: Plot for F{forecast_hour_str_fmt} saved to {output_image_full_path}")
        return True, output_image_full_path
    
    except ImportError:
        for_console_output("    A required library (pygrib, matplotlib, or cartopy) is not installed or 'Agg' backend failed for plotting.")
        return False, None
    except Exception as e:
        for_console_output(f"    Error during GRIB processing or plotting for F{forecast_hour_str_fmt}: {e}")
        traceback.print_exc()
        return False, None
    finally:
        if os.path.exists(grib_filename_temp):
            os.remove(grib_filename_temp)
            for_console_output(f"    Cleaned up temporary GRIB file: {grib_filename_temp}")
