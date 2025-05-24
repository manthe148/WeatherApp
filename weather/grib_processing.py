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


def get_latest_nam_rundate_and_hour(for_console_output=None):
    """
    Determines a recent NAM run date (YYYYMMDD) and hour string ('00', '06', '12', '18') 
    that is likely available on NOMADS. NAM has a shorter availability delay.
    """
    if for_console_output is None:
        for_console_output = print

    now_utc = datetime.now(timezone.utc)
    # NAM data might be available a bit sooner than GFS, try a ~5 hour offset
    target_time_for_run = now_utc - timedelta(hours=5) 

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

    if for_console_output: # Check if callable to avoid error if None
        for_console_output(f"  DEBUG (get_latest_nam_rundate_and_hour): Current UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%SZ')}")
        for_console_output(f"  DEBUG (get_latest_nam_rundate_and_hour): Target Time for NAM Run: {target_time_for_run.strftime('%Y-%m-%d %H:%M:%SZ')}")
        for_console_output(f"  DEBUG (get_latest_nam_rundate_and_hour): Determined NAM Run: Date={run_date_str}, Hour={run_hour_str}Z")
    return run_date_str, run_hour_str
# --- END NEW FUNCTION for NAM run time ---


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
        
        # Your existing grbs.select() call:
        select_criteria = { # Build criteria dictionary
            'level': param_details['grib_level'],
            'typeOfLevel': param_details['grib_type_of_level']
        }
        if 'select_by_name' in param_details and param_details['select_by_name']:
            select_criteria['name'] = param_details['select_by_name']
        elif 'grib_short_name' in param_details and param_details['grib_short_name']:
            select_criteria['shortName'] = param_details['grib_short_name']
        else:
            for_console_output(f"      ERROR: Neither 'select_by_name' nor 'grib_short_name' provided in param_details for {param_details.get('plot_title_param_name')}")
            grbs.close()
            return False, None

        # Add topLevel and bottomLevel to criteria if they are in param_details
        if 'grib_top_level' in param_details and param_details['grib_top_level'] is not None:
            select_criteria['topLevel'] = param_details['grib_top_level']
        if 'grib_bottom_level' in param_details and param_details['grib_bottom_level'] is not None:
            select_criteria['bottomLevel'] = param_details['grib_bottom_level']

        for_console_output(f"      Attempting grbs.select() with criteria: {select_criteria}")
        selected_messages = grbs.select(**select_criteria)









            # --- END DEBUG BLOCK --


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
        
        plot_data_values = data_values # Initialize with original values
        original_units = grib_message.units if hasattr(grib_message, 'units') else 'N/A'

        if param_details.get('needs_conversion_to_F', False):
            if hasattr(grib_message, 'units') and grib_message.units == 'K':
                plot_data_values = (data_values - 273.15) * 9/5 + 32 # K to °F
                for_console_output(f"      SUCCESS: Converted data from K to °F for {param_details['plot_title_param_name']}.")
            else:
                for_console_output(f"      WARNING: 'needs_conversion_to_F' is True, but original units are '{original_units}', not 'K'. Plotting raw data: {np.min(plot_data_values):.2f} to {np.max(plot_data_values):.2f}")

        # --- ENSURE THESE DEBUG LINES ARE PRESENT ---
        for_console_output(f"      DEBUG: Original GRIB message units: {original_units}")
        # Ensure numpy (np) is imported in your grib_processing.py for these np functions
        if 'np' in globals() and plot_data_values is not None and hasattr(plot_data_values, 'min'): 
            for_console_output(f"      DEBUG: Plotting data (should be in °F if converted) min: {np.min(plot_data_values):.2f}, max: {np.max(plot_data_values):.2f}, mean: {np.mean(plot_data_values):.2f}")
        else: 
            for_console_output(f"      DEBUG: plot_data_values type: {type(plot_data_values)}. np not available or not array-like for min/max/mean.")

        current_plot_levels = param_details.get('plot_levels')
        current_plot_levels_for_log = current_plot_levels
        if hasattr(current_plot_levels, 'tolist'): # Convert numpy array to list for cleaner printing
            current_plot_levels_for_log = current_plot_levels.tolist()
        for_console_output(f"      DEBUG: Plot levels being used: {current_plot_levels_for_log}")
        # --- END OF DEBUG LINES TO ENSURE ---

  

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


def generate_nam_parameter_plot(
    run_date_str, model_run_hour_str, forecast_hour_str_arg, 
    param_details, # Dictionary with NAM parameter specifics
    for_console_output=None
):
    if for_console_output is None:
        for_console_output = print

    current_fhr_fmt = "" 
    try:
        fhr_int = int(forecast_hour_str_arg)
        if not (0 <= fhr_int <= 84): # NAM awphys CONUS typically out to F84
             raise ValueError("Forecast hour for NAM out of range (0-84).")
        current_fhr_fmt = f"{fhr_int:02d}" # NAM often uses 2 digits for FF in awphysFF (e.g., 00, 01, ... 84)
    except ValueError as e:
        for_console_output(f"    ERROR: Invalid forecast_hour_str_arg '{forecast_hour_str_arg}' for NAM: {e}")
        return False, None

    for_console_output(f"    DEBUG (generate_nam_plot): Plotting for Param='{param_details.get('plot_title_param_name', 'N/A')}', Run='{run_date_str}/{model_run_hour_str}Z', FHR_ARG='{forecast_hour_str_arg}', Using Formatted FHR='{current_fhr_fmt}'")

    # NAM URL structure - for NAM CONUS nest (awphys files)
    # Example: nam.t<HH>z.awphys<FF>.tm00.grib2 (FF is 2-digit FHR for this product type)
    nam_url = f"https://nomads.ncep.noaa.gov/pub/data/nccf/com/nam/prod/nam.{run_date_str}/nam.t{model_run_hour_str}z.awphys{current_fhr_fmt}.tm00.grib2"
    # Note: Other NAM products or nests might have different file naming (e.g., 'firewx', 'nests/alaska/', etc.)
    # and different forecast hour formatting (sometimes 3 digits for other products).
    # This example targets the common 'awphys' CONUS files.

    file_prefix = param_details.get('output_file_prefix', 'nam_unknown') # e.g., 'nam_refc'
    local_grib_filename = f"{file_prefix}_{run_date_str}_{model_run_hour_str}_{current_fhr_fmt}_temp.grb2"

    output_image_name = f"{file_prefix}_{run_date_str}_{model_run_hour_str}z_f{current_fhr_fmt}.png"
    output_image_full_path = os.path.join(settings.MEDIA_ROOT, 'model_plots', output_image_name) 

    for_console_output(f"    DEBUG (generate_nam_plot): Temp GRIB path: {local_grib_filename}")
    for_console_output(f"    DEBUG (generate_nam_plot): Output PNG path: {output_image_full_path}")

    os.makedirs(os.path.dirname(output_image_full_path), exist_ok=True)

    if os.path.exists(output_image_full_path):
        for_console_output(f"    INFO: NAM Plot image {output_image_name} already exists. Skipping.")
        if os.path.exists(local_grib_filename): os.remove(local_grib_filename)
        return True, output_image_full_path

    for_console_output(f"  Attempting NAM {param_details.get('plot_title_param_name', 'N/A')} F{current_fhr_fmt} (Run {run_date_str} {model_run_hour_str}Z): Downloading from {nam_url}")
    try:
        response = requests.get(nam_url, stream=True, timeout=120) # NAM files can also be large
        response.raise_for_status()
        with open(local_grib_filename, 'wb') as f: 
            for chunk in response.iter_content(chunk_size=8192*4):
                f.write(chunk)
        for_console_output(f"    SUCCESS: Downloaded NAM data for F{current_fhr_fmt} to {local_grib_filename}") 
    except requests.exceptions.RequestException as e:
        for_console_output(f"    ERROR: Downloading NAM GRIB for F{current_fhr_fmt}: {e} (URL: {nam_url})")
        return False, None # Temp file cleaned in finally
    except Exception as e:
        for_console_output(f"    ERROR: Unexpected error during NAM download for F{current_fhr_fmt}: {e}")
        return False, None # Temp file cleaned in finally

    try:
        for_console_output(f"    Processing NAM GRIB file: {local_grib_filename}")
        grbs = pygrib.open(local_grib_filename)

        # Optional: Add your GRIB message listing debug loop here if needed for NAM parameters
        # print_grib_messages_debug(grbs, local_grib_filename, current_fhr_fmt, for_console_output)


# --- THIS DEBUG BLOCK IS CRUCIAL ---

        # --- START: NEW COMPREHENSIVE GRIB MESSAGE SEARCHING BLOCK ---
        # Customize the 'current_search_parameter_name' for your log message
        current_search_parameter_name = param_details.get('plot_title_param_name', 'Unknown Parameter')
        for_console_output(f"    --- Searching ALL GRIB Messages in {local_grib_filename} for relevant keywords for '{current_search_parameter_name}' (F{current_fhr_fmt}) ---")
        
        found_potential_matches = False
        # Define your keywords based on what you're currently debugging
        # Example for when you are debugging Storm Relative Helicity:
        # keywords_to_search = ['helicity', 'srh', 'hlcy', 'storm relative']
        # Example for when you are debugging Dew Point:
        # keywords_to_search = ['dewpoint', 'dew point', 'dpt', '2d', 'd2m']
        # Example for when you are debugging UPHL:
        # keywords_to_search = ['updraft', 'uphl', 'maxuh', 'helicity'] # Helicity is broad but UPHL contains it
        # Example for when you are debugging Lightning:
        # keywords_to_search = ['ltng', 'lightning']

        # FOR THE CURRENT TEST, let's use a combined list if you're testing SRH or Dew Point again.
        # Adjust this list based on the specific parameter you are trying to find in tasks.py!
        if "Dew Point" in current_search_parameter_name:
            keywords_to_search = ['dewpoint', 'dew point', 'dpt', '2d', 'd2m']
        elif "Helicity" in current_search_parameter_name: # Catches both SRH and UPHL if UPHL title has "Helicity"
            keywords_to_search = ['helicity', 'srh', 'hlcy', 'storm relative', 'uphl', 'updraft']
        elif "Lightning" in current_search_parameter_name:
            keywords_to_search = ['ltng', 'lightning']
        else:
            keywords_to_search = [] # Default to no keywords if param name doesn't give a hint
            for_console_output(f"    INFO: No specific keywords defined for parameter '{current_search_parameter_name}'. Listing all messages might be too verbose if this happens.")


        # Iterate through ALL messages in the GRIB file
        for i, msg_debug in enumerate(grbs): 
            msg_name_lower = ""
            if hasattr(msg_debug, 'name') and isinstance(msg_debug.name, str):
                msg_name_lower = msg_debug.name.lower()

            msg_short_name_lower = ""
            if hasattr(msg_debug, 'shortName') and isinstance(msg_debug.shortName, str):
                msg_short_name_lower = msg_debug.shortName.lower()
            
            keyword_found_in_message = False
            if not keywords_to_search: # If no keywords, don't try to match (or decide to print all, but that's verbose)
                pass
            else:
                for keyword in keywords_to_search:
                    if keyword in msg_name_lower or keyword in msg_short_name_lower:
                        keyword_found_in_message = True
                        break
            
            if keyword_found_in_message:
                found_potential_matches = True
                keys_to_print = [
                    'name', 'shortName', 'paramId', 'units', 
                    'level', 'typeOfLevel', 'levelName', 
                    'topLevel', 'bottomLevel', 
                    'discipline', 'parameterCategory', 'parameterNumber',
                    'forecastTime', 'stepType', 'stepRange' 
                ]
                details = []
                for key_to_print in keys_to_print:
                    value_str = "N/A (key not present or error)" # Default if not found or error
                    try:
                        # pygrib messages often behave like dicts for key access for GRIB keys
                        # or you can use specific methods if available (e.g., msg_debug.level)
                        # Using __getitem__ (like msg_debug[key_to_print]) is often more direct for GRIB keys
                        # but we'll try getattr first as it's more general for attributes/methods too.
                        # However, the error comes from __getitem__ via __getattr__ in pygrib.
                        
                        # Let's try direct key access which pygrib often uses, and catch the specific error
                        val = msg_debug[key_to_print] # Try accessing as a dictionary key
                        if val is not None:
                            value_str = f"{key_to_print}='{str(val)}'"
                        else:
                            value_str = f"{key_to_print}=None (explicitly)"
                    except RuntimeError as e_grib:
                        if "Key/value not found" in str(e_grib):
                            value_str = f"{key_to_print}=N/A (key not found)"
                        else:
                            # For other RuntimeErrors from pygrib for this key
                            value_str = f"{key_to_print}=ERROR_Runtime({str(e_grib)})" 
                    except KeyError:
                        # If it behaves purely like a dict and key is missing
                        value_str = f"{key_to_print}=N/A (KeyError)"
                    except Exception as e_other:
                        # Catch any other unexpected errors for this specific key
                        value_str = f"{key_to_print}=ERROR_Other({str(e_other)})"
                    details.append(value_str)

                
                print_msg_line = f"    Potential Match (Msg Index {i+1}/{len(grbs)}): " + ", ".join(details) # Show total messages
                for_console_output(print_msg_line)

        if not found_potential_matches and keywords_to_search: # Only print if we were actually looking for keywords
            for_console_output(f"    --- No GRIB messages found matching specified keywords {keywords_to_search} in the entire file. ---")
        elif not keywords_to_search:
             for_console_output(f"    --- No keywords specified for search; full GRIB scan for matches skipped. ---")

        grbs.seek(0) # IMPORTANT: Rewind the GRIB file iterator for the actual grbs.select() call
        for_console_output(f"    --- Finished searching. Attempting grbs.select() with current param_details. ---")
        # --- END: NEW COMPREHENSIVE GRIB MESSAGE SEARCHING BLOCK ---

        select_criteria = {}

        if 'grib_level' in param_details:
            select_criteria['level'] = param_details['grib_level']
        else:
            for_console_output(f"      ERROR: 'grib_level' missing in param_details for {param_details.get('plot_title_param_name')}")
            if grbs: grbs.close()
            return False, None # Essential to stop if basic criteria are missing
            
        if 'grib_type_of_level' in param_details:
            select_criteria['typeOfLevel'] = param_details['grib_type_of_level']
        else:
            for_console_output(f"      ERROR: 'grib_type_of_level' missing in param_details for {param_details.get('plot_title_param_name')}")
            if grbs: grbs.close()
            return False, None # Essential to stop

        # Prefer select_by_name if provided, otherwise use grib_short_name
        if 'select_by_name' in param_details and param_details['select_by_name']:
            select_criteria['name'] = param_details['select_by_name']
            for_console_output(f"      Selecting by full name: '{param_details['select_by_name']}'")
        elif 'grib_short_name' in param_details and param_details['grib_short_name']:
            select_criteria['shortName'] = param_details['grib_short_name']
            for_console_output(f"      Selecting by shortName: '{param_details['grib_short_name']}'")
        else:
            # If neither is provided, it's an error in param_details setup
            for_console_output(f"      ERROR: Neither 'select_by_name' nor 'grib_short_name' key found or has value in param_details for {param_details.get('plot_title_param_name')}")
            if grbs: grbs.close()
            return False, None 

        # Add topLevel and bottomLevel to criteria if they are in param_details and not None
        if 'grib_top_level' in param_details and param_details['grib_top_level'] is not None:
            select_criteria['topLevel'] = param_details['grib_top_level']
        if 'grib_bottom_level' in param_details and param_details['grib_bottom_level'] is not None:
            select_criteria['bottomLevel'] = param_details['grib_bottom_level']
        
        for_console_output(f"      Attempting grbs.select() with criteria: {select_criteria}")
        try:
            selected_messages = grbs.select(**select_criteria)
        except ValueError as e: # Catch "no matches found" specifically
            if "no matches found" in str(e).lower(): # make case insensitive
                 for_console_output(f"      ERROR from grbs.select(): no matches found for criteria {select_criteria}")
                 selected_messages = [] # Ensure it's an empty list
            else:
                raise # Re-raise other ValueErrors
        # --- END: ROBUST SELECTION CRITERIA LOGIC ---
        
        grib_message = None
        if selected_messages:
            grib_message = selected_messages[0]
            for_console_output(f"      SUCCESS: Found GRIB message for {param_details.get('plot_title_param_name', 'N/A')} using criteria {select_criteria}")
        else: 
            # This handles the case where selected_messages is empty from the try-except block above
            for_console_output(f"      ERROR: Could not find GRIB message for {param_details.get('plot_title_param_name', 'N/A')} with criteria {select_criteria} (select call returned no messages or 'no matches found' was caught).")
            if grbs: grbs.close()
            return False, None


        # --- END DEBUG BLOCK ---


        selected_messages = grbs.select(
            shortName=param_details['grib_short_name'],
            level=param_details['grib_level'],
            typeOfLevel=param_details['grib_type_of_level']
        )

        grib_message = None
        if selected_messages:
            grib_message = selected_messages[0]
            for_console_output(f"    Found GRIB message for NAM {param_details.get('plot_title_param_name', 'N/A')}: {grib_message.name} (L{grib_message.level} {grib_message.typeOfLevel})")

        if not grib_message:
            for_console_output(f"    ERROR: Could not find GRIB message for {param_details['plot_title_param_name']} (shortName '{param_details['grib_short_name']}', etc.) in NAM file for F{current_fhr_fmt}.")
            grbs.close() 
            return False, None

        data_values = grib_message.values
        lats, lons = grib_message.latlons()
        # NAM data does not require Fahrenheit conversion for reflectivity or CAPE
        plot_data_values = data_values 

        plot_data_values = data_values # Initialize
        original_units = "N/A"
        if hasattr(grib_message, 'units') and grib_message.units is not None:
            original_units = grib_message.units
            
        for_console_output(f"      PRINT_DEBUG_STEP_1: Original GRIB units = '{original_units}'")

        if param_details.get('needs_conversion_to_F', False):
            if original_units == 'K':
                plot_data_values = (data_values - 273.15) * 9/5 + 32 # K to °F
                for_console_output(f"      PRINT_DEBUG_STEP_2: Data converted from K to °F.")
            else:
                 for_console_output(f"      PRINT_DEBUG_STEP_2: WARNING - 'needs_conversion_to_F' is True, but original units '{original_units}' != 'K'. Using raw data.")
        else:
             for_console_output(f"      PRINT_DEBUG_STEP_2: No temperature conversion requested or applied.")
            
            # Ensure numpy (np) is imported at the top of grib_processing.py
        if 'np' in globals() and hasattr(plot_data_values, 'shape') and plot_data_values.size > 0:
            min_val = np.nanmin(plot_data_values)
            max_val = np.nanmax(plot_data_values)
            mean_val = np.nanmean(plot_data_values)
            for_console_output(f"      PRINT_DEBUG_STEP_3: plot_data_values (post-conversion, for plotting) - Min={min_val:.2f}, Max={max_val:.2f}, Mean={mean_val:.2f}, Shape={plot_data_values.shape}")
        else:
            for_console_output(f"      PRINT_DEBUG_STEP_3: plot_data_values could not be analyzed (np not found, or data is None/empty). Type: {type(plot_data_values)}")

        current_plot_levels = param_details.get('plot_levels')
        current_plot_levels_for_log = "N/A"
        if current_plot_levels is not None:
            current_plot_levels_for_log = str(current_plot_levels.tolist() if hasattr(current_plot_levels, 'tolist') else current_plot_levels)
        for_console_output(f"      PRINT_DEBUG_STEP_4: Plot levels being used: {current_plot_levels_for_log}")
            
   


        grbs.close()
        for_console_output(f"    NAM GRIB data processed for {param_details['plot_title_param_name']} F{current_fhr_fmt}.")

        for_console_output(f"    Generating NAM plot for {param_details['plot_title_param_name']} F{current_fhr_fmt}...")
        fig = plt.figure(figsize=(12, 9)) 
        ax = plt.axes(projection=ccrs.PlateCarree()) 

        # NAM is North America focused, adjust default extent.
        # These bounds roughly cover CONUS and are good for NAM CONUS nest.
        ax.set_extent([-125, -65, 23, 52], crs=ccrs.PlateCarree()) 

        ax.add_feature(cfeature.COASTLINE, linewidth=0.8, edgecolor='dimgray', zorder=2)
        ax.add_feature(cfeature.BORDERS, linestyle=':', linewidth=0.6, edgecolor='dimgray', zorder=2)
        ax.add_feature(cfeature.STATES, linestyle=':', linewidth=0.6, edgecolor='dimgray', zorder=2)

        plot_levels_val = param_details.get('plot_levels')
        plot_cmap_val = param_details.get('plot_cmap', 'jet')

        if plot_levels_val is not None and hasattr(plot_levels_val, '__len__') and len(plot_levels_val) > 0 :
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
        ax.set_title(f"NAM {param_details['plot_title_param_name']}\nRun: {run_date_str} {model_run_hour_str}Z - Forecast: F{current_fhr_fmt}", fontsize=12)

        # Add Watermark
        watermark_text = "myweathersite.com" # <<< *** REPLACE THIS ***
        fig.text(0.98, 0.02, watermark_text, fontsize=20, color='black', alpha=0.6,
                 ha='right', va='bottom', transform=fig.transFigure, zorder=10)

        for_console_output(f"    DEBUG: Attempting to savefig to: {output_image_full_path}")
        plt.savefig(output_image_full_path, bbox_inches='tight', pad_inches=0.1, dpi=150)
        plt.close(fig)
        for_console_output(f"    SUCCESS: Plot for NAM {param_details['plot_title_param_name']} F{current_fhr_fmt} saved to {output_image_full_path}")
        return True, output_image_full_path

    except ImportError:
        for_console_output("    ERROR: Plotting library or pygrib missing or 'Agg' backend issue.")
        return False, None
    except Exception as e:
        for_console_output(f"    ERROR: During NAM GRIB processing or plotting for {param_details['plot_title_param_name']} F{current_fhr_fmt}: {e}")
        traceback.print_exc()
        return False, None
    finally:
        if os.path.exists(local_grib_filename):
            os.remove(local_grib_filename)
            for_console_output(f"    INFO: Cleaned up temporary NAM GRIB file: {local_grib_filename}")
# --- END NEW FUNCTION for NAM plots ---

# --- Helper function for views to find image details with fallback ---
def get_gfs_image_details_with_fallback(requested_fhr_str, output_file_prefix, for_console_output=None):
    if for_console_output is None:
        for_console_output = print

    fhr_to_check = "006"; actual_fhr_for_return = "006"
    try:
        fhr_int = int(requested_fhr_str)
        actual_fhr_for_return = f"{fhr_int:03d}"
        fhr_to_check = actual_fhr_for_return # Use validated FHR for checks
    except ValueError:
        for_console_output(f"  Warning (get_image_details): Invalid requested_fhr '{requested_fhr_str}', using default '006'.")
        actual_fhr_for_return = "006" # Keep fhr_to_check also as "006"

    def get_run_cycle_parts(dt_object):
        # ... (as before) ...
        run_date = dt_object.strftime("%Y%m%d")
        hour_val = dt_object.hour
        if hour_val >= 18: run_h_str = "18"
        elif hour_val >= 12: run_h_str = "12"
        elif hour_val >= 6: run_h_str = "06"
        else: run_h_str = "00"
        return run_date, run_h_str

    def construct_run_datetime_utc(date_str, hour_str):
        try:
            return datetime(
                int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]),
                int(hour_str), tzinfo=timezone.utc)
        except ValueError: return None

    # Attempt 1: Latest Expected Run
    now_utc = datetime.now(timezone.utc)
    latest_expected_run_time = now_utc - timedelta(hours=7) 
    run_date_str, model_run_hour_str = get_run_cycle_parts(latest_expected_run_time)

    expected_image_filename = f"{output_file_prefix}_{run_date_str}_{model_run_hour_str}z_f{fhr_to_check}.png"
    full_image_filesystem_path = os.path.join(settings.MEDIA_ROOT, 'model_plots', expected_image_filename)

    if os.path.exists(full_image_filesystem_path):
        image_url = settings.MEDIA_URL + os.path.join('model_plots', expected_image_filename)
        run_dt_utc = construct_run_datetime_utc(run_date_str, model_run_hour_str)
        display_message = f"GFS Plot - F{fhr_to_check} (Run: {run_date_str} {model_run_hour_str}Z)"
        return {
            'image_exists': True, 'image_url': image_url, 'display_message': display_message,
            'run_datetime_utc': run_dt_utc, 'actual_fhr': fhr_to_check
        }

    # Attempt 2: Previous Run
    latest_run_start_dt = construct_run_datetime_utc(run_date_str, model_run_hour_str)
    if latest_run_start_dt: # Check if latest_run_start_dt was successfully created
        previous_expected_run_time = latest_run_start_dt - timedelta(hours=6)
        prev_run_date_str, prev_model_run_hour_str = get_run_cycle_parts(previous_expected_run_time)

        expected_image_filename_prev = f"{output_file_prefix}_{prev_run_date_str}_{prev_model_run_hour_str}z_f{fhr_to_check}.png"
        full_image_filesystem_path_prev = os.path.join(settings.MEDIA_ROOT, 'model_plots', expected_image_filename_prev)

        if os.path.exists(full_image_filesystem_path_prev):
            image_url = settings.MEDIA_URL + os.path.join('model_plots', expected_image_filename_prev)
            run_dt_utc = construct_run_datetime_utc(prev_run_date_str, prev_model_run_hour_str)
            display_message = f"GFS Plot - F{fhr_to_check} (Previous Run: {prev_run_date_str} {prev_model_run_hour_str}Z - Latest not available)"
            return {
                'image_exists': True, 'image_url': image_url, 'display_message': display_message,
                'run_datetime_utc': run_dt_utc, 'actual_fhr': fhr_to_check
            }

    # Fallback: No image found
    run_dt_utc_targeted = construct_run_datetime_utc(run_date_str, model_run_hour_str) # The one we initially targeted
    display_message = f"GFS Plot - F{fhr_to_check} (Target Run: {run_date_str} {model_run_hour_str}Z) not available."
    return {
        'image_exists': False, 'image_url': None, 'display_message': display_message,
        'run_datetime_utc': run_dt_utc_targeted, 'actual_fhr': fhr_to_check
    }
