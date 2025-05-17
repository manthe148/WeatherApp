# weather/grib_processing.py
import requests
import os
import pygrib
import numpy as np
import matplotlib
matplotlib.use('Agg') # Use non-interactive backend for scripts/tasks
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from datetime import datetime, timedelta, timezone
from django.conf import settings # For MEDIA_ROOT and MEDIA_URL
import traceback

# --- Helper function to determine latest GFS run details ---
def get_latest_gfs_rundate_and_hour(for_console_output=None):
    """
    Determines a recent GFS run date (YYYYMMDD) and hour string ('00', '06', '12', '18') 
    that is likely available on NOMADS.
    'for_console_output' is a callable for logging (e.g., print or self.stdout.write).
    """
    if for_console_output is None:
        for_console_output = print 

    now_utc = datetime.now(timezone.utc)
    target_time_for_run = now_utc - timedelta(hours=7) # Approx. 7-hour offset
    
    run_date_str = target_time_for_run.strftime("%Y%m%d")
    hour_val = target_time_for_run.hour

    if hour_val >= 18:
        run_hour_str = "18"
    elif hour_val >= 12:
        run_hour_str = "12"
    elif hour_val >= 6:
        run_hour_str = "06"
    else:
        run_hour_str = "00"
    
    for_console_output(f"  DEBUG (get_latest_gfs_rundate_and_hour): Current UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%SZ')}")
    for_console_output(f"  DEBUG (get_latest_gfs_rundate_and_hour): Target Time for Run: {target_time_for_run.strftime('%Y-%m-%d %H:%M:%SZ')}")
    for_console_output(f"  DEBUG (get_latest_gfs_rundate_and_hour): Determined GFS Run: Date={run_date_str}, Hour={run_hour_str}Z")
    return run_date_str, run_hour_str

# --- Main function to generate a GFS parameter plot ---
def generate_gfs_parameter_plot(
    run_date_str, model_run_hour_str, forecast_hour_str_arg, # Argument from task/command
    param_details, 
    for_console_output=None
):
    if for_console_output is None:
        for_console_output = print

    current_fhr_fmt = "" # This will be the formatted "006", "012", etc.
    try:
        fhr_int = int(forecast_hour_str_arg)
        if not (0 <= fhr_int <= 384):
             raise ValueError("Forecast hour out of typical GFS range.")
        current_fhr_fmt = f"{fhr_int:03d}" 
    except ValueError as e:
        for_console_output(f"    ERROR: Invalid forecast_hour_str_arg '{forecast_hour_str_arg}': {e}")
        return False, None

    for_console_output(f"    DEBUG (generate_plot): Init for Param='{param_details.get('plot_title_param_name', 'N/A')}', Run='{run_date_str}/{model_run_hour_str}Z', FHR_ARG='{forecast_hour_str_arg}', Using Formatted FHR='{current_fhr_fmt}'")

    gfs_url = f"https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/gfs.{run_date_str}/{model_run_hour_str}/atmos/gfs.t{model_run_hour_str}z.pgrb2.0p25.f{current_fhr_fmt}"
    
    file_prefix = param_details.get('output_file_prefix', 'gfs_unknown')
    # Define temporary GRIB filename using current_fhr_fmt to ensure it's unique FOR THIS CALL
    local_grib_filename = f"{file_prefix}_{run_date_str}_{model_run_hour_str}_{current_fhr_fmt}_temp.grb2"
    
    output_image_name = f"{file_prefix}_{run_date_str}_{model_run_hour_str}z_f{current_fhr_fmt}.png"
    output_image_full_path = os.path.join(settings.MEDIA_ROOT, 'model_plots', output_image_name)
    
    for_console_output(f"    DEBUG (generate_plot): Temp GRIB path to be used: {local_grib_filename}")
    for_console_output(f"    DEBUG (generate_plot): Output PNG path: {output_image_full_path}")
    
    os.makedirs(os.path.dirname(output_image_full_path), exist_ok=True)

    if os.path.exists(output_image_full_path):
        for_console_output(f"    INFO: Plot image {output_image_name} already exists. Skipping generation for F{current_fhr_fmt}.")
        if os.path.exists(local_grib_filename): # Clean up old temp file if it exists for some reason
             os.remove(local_grib_filename)
        return True, output_image_full_path

    for_console_output(f"  Attempting {param_details.get('plot_title_param_name', 'N/A')} GFS F{current_fhr_fmt} (Run {run_date_str} {model_run_hour_str}Z): Downloading from {gfs_url}")
    try:
        response = requests.get(gfs_url, stream=True, timeout=180)
        response.raise_for_status()
        with open(local_grib_filename, 'wb') as f: # Use the unique local_grib_filename
            for chunk in response.iter_content(chunk_size=8192*4):
                f.write(chunk)
        for_console_output(f"    SUCCESS: Downloaded GFS data for F{current_fhr_fmt} to {local_grib_filename}") 
    except requests.exceptions.RequestException as e:
        for_console_output(f"    ERROR: Downloading GRIB file for {param_details.get('plot_title_param_name', 'N/A')} F{current_fhr_fmt}: {e}")
        return False, None # Temp file cleaned in finally
    except Exception as e:
        for_console_output(f"    ERROR: Unexpected error during download for F{current_fhr_fmt}: {e}")
        return False, None # Temp file cleaned in finally

    try:
        for_console_output(f"    Processing GRIB file: {local_grib_filename}")
        grbs = pygrib.open(local_grib_filename) # Open the unique local_grib_filename
        
        # Optional GRIB message listing debug
        # print_grib_messages_debug(grbs, local_grib_filename, current_fhr_fmt, for_console_output)

        selected_messages = grbs.select(
            shortName=param_details['grib_short_name'],
            level=param_details['grib_level'],
            typeOfLevel=param_details['grib_type_of_level']
        )
        
        grib_message = None
        if selected_messages:
            grib_message = selected_messages[0]
            for_console_output(f"    Found GRIB message for {param_details.get('plot_title_param_name', 'N/A')}: {grib_message.name} (level {grib_message.level} {grib_message.typeOfLevel})")
        
        if not grib_message:
            for_console_output(f"    ERROR: Could not find GRIB message for {param_details['plot_title_param_name']} (shortName '{param_details['grib_short_name']}', level {param_details['grib_level']}, typeOfLevel '{param_details['grib_type_of_level']}') in file for F{current_fhr_fmt}.")
            grbs.close() 
            return False, None

        data_values = grib_message.values
        lats, lons = grib_message.latlons()
        
        plot_data_values = data_values 
        if param_details.get('needs_conversion_to_F', False) and hasattr(grib_message, 'units') and grib_message.units == 'K':
            plot_data_values = (data_values - 273.15) * 9/5 + 32
            for_console_output(f"    Converted data from K to °F for {param_details['plot_title_param_name']}.")
        
        grbs.close()
        for_console_output(f"    GRIB data processed for {param_details['plot_title_param_name']} F{current_fhr_fmt}.")

        for_console_output(f"    Generating plot for {param_details['plot_title_param_name']} F{current_fhr_fmt}...")
        fig = plt.figure(figsize=(12, 9))
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_extent([-125, -65, 23, 50], crs=ccrs.PlateCarree())
        ax.add_feature(cfeature.COASTLINE, linewidth=0.8, edgecolor='dimgray', zorder=2)
        ax.add_feature(cfeature.BORDERS, linestyle=':', linewidth=0.6, edgecolor='dimgray', zorder=2)
        ax.add_feature(cfeature.STATES, linestyle=':', linewidth=0.6, edgecolor='dimgray', zorder=2)
        
        plot_levels_val = param_details.get('plot_levels')
        plot_cmap_val = param_details.get('plot_cmap', 'jet')

        if plot_levels_val is not None and hasattr(plot_levels_val, '__len__') and len(plot_levels_val) > 0 : # Check if it's a list/array and has items
            vmin_val = plot_levels_val[0]
            vmax_val = plot_levels_val[-1]
            mesh = plt.pcolormesh(lons, lats, plot_data_values, 
                                  transform=ccrs.PlateCarree(), cmap=plot_cmap_val,
                                  vmin=vmin_val, vmax=vmax_val, shading='gouraud', zorder=1) 
            cb = plt.colorbar(mesh, ax=ax, orientation='horizontal', label=param_details['plot_unit_label'], 
                              pad=0.05, shrink=0.7, aspect=30, extend='both')
        else: 
            mesh = plt.pcolormesh(lons, lats, plot_data_values, 
                                  transform=ccrs.PlateCarree(), cmap=plot_cmap_val, shading='gouraud', zorder=1)
            cb = plt.colorbar(mesh, ax=ax, orientation='horizontal', label=param_details['plot_unit_label'], 
                              pad=0.05, shrink=0.7, aspect=30)
        
        cb.ax.tick_params(labelsize=8) 
        ax.set_title(f"GFS {param_details['plot_title_param_name']}\nRun: {run_date_str} {model_run_hour_str}Z - Forecast: F{current_fhr_fmt}", fontsize=12)
        
        watermark_text = "myweathersite.com" # <<< REPLACE THIS WITH YOUR ACTUAL SITE/COMPANY NAME
        fig.text(0.98, 0.02, watermark_text, fontsize=20, color='black', alpha=0.9,
                 ha='right', va='bottom', transform=fig.transFigure, zorder=10)
        
        for_console_output(f"    DEBUG: Attempting to savefig to: {output_image_full_path}")
        plt.savefig(output_image_full_path, bbox_inches='tight', pad_inches=0.1, dpi=150)
        plt.close(fig)
        for_console_output(f"    SUCCESS: Plot for {param_details['plot_title_param_name']} F{current_fhr_fmt} saved to {output_image_full_path}")
        return True, output_image_full_path
    
    except ImportError:
        for_console_output("    ERROR: Plotting library or pygrib missing or 'Agg' backend issue.")
        return False, None
    except Exception as e:
        for_console_output(f"    ERROR: During GRIB processing or plotting for {param_details['plot_title_param_name']} F{current_fhr_fmt}: {e}")
        traceback.print_exc()
        return False, None
    finally:
        if os.path.exists(local_grib_filename): # Ensure cleanup of the unique temporary GRIB file
            os.remove(local_grib_filename)
            for_console_output(f"    INFO: Cleaned up temporary GRIB file: {local_grib_filename}")

# --- Helper function for views to find image details with fallback ---
def get_gfs_image_details_with_fallback(requested_fhr_str, output_file_prefix, for_console_output=None):
    if for_console_output is None:
        for_console_output = print

    fhr_to_check = "006" 
    try:
        fhr_int = int(requested_fhr_str)
        fhr_to_check = f"{fhr_int:03d}"
    except ValueError:
        for_console_output(f"  Warning (get_image_details): Invalid requested_fhr '{requested_fhr_str}', using default '{fhr_to_check}'.")
    
    def get_run_cycle_parts(dt_object):
        run_date = dt_object.strftime("%Y%m%d")
        hour_val = dt_object.hour
        if hour_val >= 18: run_h_str = "18"
        elif hour_val >= 12: run_h_str = "12"
        elif hour_val >= 6: run_h_str = "06"
        else: run_h_str = "00"
        return run_date, run_h_str

    now_utc = datetime.now(timezone.utc)
    latest_expected_run_time = now_utc - timedelta(hours=7) 
    run_date_str, model_run_hour_str = get_run_cycle_parts(latest_expected_run_time)
    
    for_console_output(f"  Image Check (Latest): Run {run_date_str} {model_run_hour_str}Z, FHR {fhr_to_check}, Prefix {output_file_prefix}")
    expected_image_filename = f"{output_file_prefix}_{run_date_str}_{model_run_hour_str}z_f{fhr_to_check}.png"
    full_image_filesystem_path = os.path.join(settings.MEDIA_ROOT, 'model_plots', expected_image_filename)

    if os.path.exists(full_image_filesystem_path):
        image_url = settings.MEDIA_URL + os.path.join('model_plots', expected_image_filename)
        display_message = f"GFS Plot - F{fhr_to_check} (Run: {run_date_str} {model_run_hour_str}Z)"
        for_console_output(f"    Found latest image: {image_url}")
        return {
            'image_exists': True, 'image_url': image_url, 'display_message': display_message,
            'actual_run_date': run_date_str, 'actual_run_hour': model_run_hour_str, 'actual_fhr': fhr_to_check
        }

    for_console_output(f"    Latest image not found ({expected_image_filename}). Trying previous run.")
    try:
        latest_run_cycle_start_dt = datetime(int(run_date_str[:4]), int(run_date_str[4:6]), int(run_date_str[6:8]), int(model_run_hour_str), 0, 0, tzinfo=timezone.utc)
    except ValueError:
        for_console_output(f"    ERROR (get_image_details): Could not parse latest_run_start_dt from {run_date_str} {model_run_hour_str}Z")
        display_message = f"GFS Plot - F{fhr_to_check} (Target Run: {run_date_str} {model_run_hour_str}Z) is not available. Error determining previous run."
        return {
            'image_exists': False, 'image_url': None, 'display_message': display_message,
            'actual_run_date': run_date_str, 'actual_run_hour': model_run_hour_str, 'actual_fhr': fhr_to_check
        }
    previous_expected_run_time = latest_run_cycle_start_dt - timedelta(hours=6)
    prev_run_date_str, prev_model_run_hour_str = get_run_cycle_parts(previous_expected_run_time)
    
    for_console_output(f"  Image Check (Previous): Run {prev_run_date_str} {prev_model_run_hour_str}Z, FHR {fhr_to_check}, Prefix {output_file_prefix}")
    expected_image_filename_prev = f"{output_file_prefix}_{prev_run_date_str}_{prev_model_run_hour_str}z_f{fhr_to_check}.png"
    full_image_filesystem_path_prev = os.path.join(settings.MEDIA_ROOT, 'model_plots', expected_image_filename_prev)

    if os.path.exists(full_image_filesystem_path_prev):
        image_url = settings.MEDIA_URL + os.path.join('model_plots', expected_image_filename_prev)
        display_message = f"GFS Plot - F{fhr_to_check} (Previous Run: {prev_run_date_str} {prev_model_run_hour_str}Z - Latest not available)"
        for_console_output(f"    Found previous run image: {image_url}")
        return {
            'image_exists': True, 'image_url': image_url, 'display_message': display_message,
            'actual_run_date': prev_run_date_str, 'actual_run_hour': prev_model_run_hour_str, 'actual_fhr': fhr_to_check
        }
    
    for_console_output(f"    Previous run image also not found ({expected_image_filename_prev}).")
    display_message = f"GFS Plot - F{fhr_to_check} (Target Run: {run_date_str} {model_run_hour_str}Z) is not available. Previous run also not found."
    return {
        'image_exists': False, 'image_url': None, 'display_message': display_message,
        'actual_run_date': run_date_str, 'actual_run_hour': model_run_hour_str, 'actual_fhr': fhr_to_check
    }
