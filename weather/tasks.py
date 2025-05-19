# weather/tasks.py

from weather.grib_processing import (
    get_latest_gfs_rundate_and_hour, 
    generate_gfs_parameter_plot, # Or generate_model_parameter_plot if you renamed the GFS one
    get_latest_nam_rundate_and_hour,    # <<< NEW IMPORT
    generate_nam_parameter_plot     # <<< NEW IMPORT
)

try:
    import numpy as np
except ImportError:
    print("WARNING: NumPy not imported in tasks.py, but grib_processing might need it for plot_levels.")
    np = None # Fallback, though grib_processing defines its own levels


from weather.grib_processing import get_latest_gfs_rundate_and_hour, generate_gfs_parameter_plot
from django_q.tasks import schedule, Schedule # For potential re-scheduling or checking
from datetime import datetime, timezone, timedelta
import os
from django.conf import settings

def automated_gfs_plot_generation(*args, **kwargs): # Added *args, **kwargs
    print(f"[{datetime.now(timezone.utc).isoformat()}] Task: automated_gfs_plot_generation starting...")

    run_date_str, model_run_hour_str = get_latest_gfs_rundate_and_hour(print)

    forecast_hours_to_generate = [f"{h:03d}" for h in range(0, 121, 6)] # e.g., F000, F006, ... F120

    # --- DEFINE PARAMETERS TO PLOT ---
    parameters_to_plot = [
        {
            'grib_short_name': '2t', 'grib_level': 2, 'grib_type_of_level': 'heightAboveGround',
            'output_file_prefix': 'gfs_t2m', 'plot_title_param_name': '2m Temperature',
            'plot_unit_label': 'Temperature (deg F)', 'plot_cmap': 'jet',
            'plot_levels': np.arange(0, 105, 5) if np else None, # Use np if available
            'needs_conversion_to_F': True
        },
        {
            'grib_short_name': 'cape', 'grib_level': 0, 'grib_type_of_level': 'surface', # Surface Based CAPE
            'output_file_prefix': 'gfs_sbcape', 'plot_title_param_name': 'Surface CAPE',
            'plot_unit_label': 'SBCAPE (J/kg)', 'plot_cmap': 'magma_r', # Or 'viridis', 'plasma'
            'plot_levels': np.arange(0, 5001, 250) if np else None, # Levels for CAPE
            'needs_conversion_to_F': False
        },
        { # --- ADD OR VERIFY THIS ENTRY FOR COMPOSITE REFLECTIVITY ---
           'grib_short_name': 'refc', 
           'grib_level': 0, 
           'grib_type_of_level': 'atmosphere', # Was 'entireAtmosphereConsideredAsASingleLayer'
           'output_file_prefix': 'gfs_refc', 
           'plot_title_param_name': 'Sim. Comp. Reflectivity',
           'plot_unit_label': 'Reflectivity (dBZ)', 
           'plot_cmap': 'jet', # Or 'turbo'
           'plot_levels': list(range(5, 76, 5)) if np is None else np.arange(5, 76, 5),
           'needs_conversion_to_F': False
       }
    # --- END REFLECTIVITY ENTRY ---

    ]
    # --- END PARAMETER DEFINITIONS ---

    print(f"  Target GFS Run: {run_date_str} {model_run_hour_str}Z")
    print(f"  Will attempt to generate plots for FHRs: {forecast_hours_to_generate}")
    print(f"  For parameters: {[p['plot_title_param_name'] for p in parameters_to_plot]}")

    generated_count_total = 0
    failed_count_total = 0

    for param_config in parameters_to_plot:
        print(f"\n  Processing Parameter: {param_config['plot_title_param_name']}")
        current_param_generated = 0
        current_param_failed = 0
        for fhr_str in forecast_hours_to_generate:
            # Check if image for this specific run, param, and fhr already exists
            output_image_name_check = f"{param_config['output_file_prefix']}_{run_date_str}_{model_run_hour_str}z_f{fhr_str}.png"
            output_image_full_path_check = os.path.join(settings.MEDIA_ROOT, 'model_plots', output_image_name_check)

            if os.path.exists(output_image_full_path_check):
                print(f"    Plot for {param_config['plot_title_param_name']} F{fhr_str} (Run: {run_date_str} {model_run_hour_str}Z) already exists. Skipping.")
                current_param_generated +=1
                continue

            print(f"    Generating {param_config['plot_title_param_name']} plot for F{fhr_str}...")
            # Ensure generate_gfs_parameter_plot is correctly imported if it's in grib_processing.py
            success, _ = generate_gfs_parameter_plot( # Call the generic plot function
                run_date_str,
                model_run_hour_str,
                fhr_str,
                param_config, # Pass the whole details dictionary
                print 
            )
            if success:
                current_param_generated += 1
            else:
                current_param_failed += 1

        generated_count_total += current_param_generated
        failed_count_total += current_param_failed
        print(f"  Finished processing for {param_config['plot_title_param_name']}. Generated: {current_param_generated}, Failed: {current_param_failed}")

    print(f"[{datetime.now(timezone.utc).isoformat()}] Task: automated_gfs_plot_generation finished. Total Generated: {generated_count_total}, Total Failed: {failed_count_total} for run {run_date_str} {model_run_hour_str}Z.")



def automated_nam_plot_generation(*args, **kwargs): # Accept args for scheduler
    print(f"[{datetime.now(timezone.utc).isoformat()}] Task: automated_nam_plot_generation starting...")

    run_date_str, model_run_hour_str = get_latest_nam_rundate_and_hour(print)

    # NAM forecast hours: Hourly out to F36, then 3-hourly out to F84 for awphys products.
    # Let's generate a selection: e.g., F00, F01, F02, F03, then every 3 hours.
    forecast_hours_to_generate = []
    for h in range(0, 37): # Hourly from 00 to 36
        forecast_hours_to_generate.append(f"{h:02d}")
    for h in range(39, 85, 3): # 3-hourly from 39 to 84
        forecast_hours_to_generate.append(f"{h:02d}")
    # Remove duplicates if any and sort (though above logic should be fine)
    # forecast_hours_to_generate = sorted(list(set(forecast_hours_to_generate)))

    # --- DEFINE NAM PARAMETERS TO PLOT ---
    # For now, just Simulated Composite Reflectivity
    # Ensure numpy (np) is imported at the top of tasks.py if using np.arange here
    nam_parameters_to_plot = [
        { 
           'grib_short_name': 'refc', 
           'grib_level': 0, 
           'grib_type_of_level': 'atmosphereSingleLayer', # Was 'entireAtmosphereConsideredAsASingleLayer'
           'output_file_prefix': 'nam_refc', 
           'plot_title_param_name': 'Sim. Comp. Reflectivity',
           'plot_unit_label': 'Reflectivity (dBZ)', 
           'plot_cmap': 'jet', 
           'plot_levels': list(range(5, 76, 5)) if np is None else np.arange(5, 76, 5),
           'needs_conversion_to_F': False 
        },
        { 
            'grib_short_name': 'cape', 'grib_level': 0, 'grib_type_of_level': 'surface',
            'output_file_prefix': 'nam_sbcape', 'plot_title_param_name': 'Surface CAPE',
            'plot_unit_label': 'SBCAPE (J/kg)', 'plot_cmap': 'magma_r',
            'plot_levels': np.arange(0, 5001, 250),
            'needs_conversion_to_F': False
        },
        { 
            'grib_short_name': '2d', 
            'grib_level': 2, 
            'grib_type_of_level': 'heightAboveGround',
            'output_file_prefix': 'gfs_dewp2m', 
            'plot_title_param_name': '2m Dew Point',
            'plot_unit_label': 'Dew Point (°F)', 
            'plot_cmap': 'BuGn', # Colormap
            'plot_levels': np.arange(0, 91, 2), # 0°F to 90°F in steps of 2°F
            'needs_conversion_to_F': True 
        },
        { # Supercell Composite - GRIB DETAILS ARE EDUCATED GUESSES - VERIFY!
            'grib_short_name': 'compsup', # Example shortName, might be just 'scp' or require full Name search
            'grib_level': 0, 
            'grib_type_of_level': 'surface', 
            'output_file_prefix': 'nam_scp', 'plot_title_param_name': 'NAM Supercell Composite',
            'plot_unit_label': 'SCP (Index)', 'plot_cmap': 'YlOrRd',
            'plot_levels': np.arange(0, 21, 1),
            'needs_conversion_to_F': False
        },
        { # Significant Tornado Parameter - GRIB DETAILS ARE EDUCATED GUESSES - VERIFY!
            'grib_short_name': 'sigtor', # Example shortName, might be 'stp', 'sigtidx' or require full Name search
            'grib_level': 0, 
            'grib_type_of_level': 'surface', 
            'output_file_prefix': 'nam_stp', 'plot_title_param_name': 'NAM Sig. Tornado Param.',
            'plot_unit_label': 'STP (Index)', 'plot_cmap': 'PuRd',
            'plot_levels': np.arange(0, 11, 0.5),
            'needs_conversion_to_F': False
        }
    ]


    # --- END NAM PARAMETER DEFINITIONS ---

    print(f"  Target NAM Run: {run_date_str} {model_run_hour_str}Z")
    print(f"  Will attempt to generate NAM plots for FHRs: {forecast_hours_to_generate}")
    print(f"  For NAM parameters: {[p['plot_title_param_name'] for p in nam_parameters_to_plot]}")

    generated_count_total = 0
    failed_count_total = 0

    for param_config in nam_parameters_to_plot:
        print(f"\n  Processing NAM Parameter: {param_config['plot_title_param_name']}")
        current_param_generated = 0
        current_param_failed = 0
        for fhr_str in forecast_hours_to_generate:
            # Check if image for this specific run, param, and fhr already exists
            output_image_name_check = f"{param_config['output_file_prefix']}_{run_date_str}_{model_run_hour_str}z_f{fhr_str}.png"
            output_image_full_path_check = os.path.join(settings.MEDIA_ROOT, 'model_plots', output_image_name_check)

            if os.path.exists(output_image_full_path_check):
                print(f"    Plot for NAM {param_config['plot_title_param_name']} F{fhr_str} (Run {run_date_str} {model_run_hour_str}Z) already exists. Skipping.")
                current_param_generated +=1
                continue

            print(f"    Generating NAM {param_config['plot_title_param_name']} plot for F{fhr_str}...")

            success, _ = generate_nam_parameter_plot( # Call the NAM-specific plot function
                run_date_str,
                model_run_hour_str,
                fhr_str,        # This is the argument for forecast_hour_str_arg
                param_config,   # Pass the whole details dictionary
                print           # Pass print for logging
            )
            if success:
                current_param_generated += 1
            else:
                current_param_failed += 1

        generated_count_total += current_param_generated
        failed_count_total += current_param_failed
        print(f"  Finished processing for NAM {param_config['plot_title_param_name']}. Generated this run: {current_param_generated}, Failed this run: {current_param_failed}")

    print(f"[{datetime.now(timezone.utc).isoformat()}] Task: automated_nam_plot_generation finished. Total new/updated NAM plots: {generated_count_total}, Total failed: {failed_count_total} for run {run_date_str} {model_run_hour_str}Z.")
