# weather/tasks.py (or a new file like weather/radar_tasks.py)

# Ensure these imports are at the top of your file
import boto3
from botocore import UNSIGNED # For accessing public S3 bucket without credentials for download
from botocore.config import Config as BotoConfig
import os
import gzip
import shutil
import pyart # Assuming you will use Py-ART for processing
from django.conf import settings
from datetime import datetime, timezone, timedelta

# ... your existing task functions (automated_gfs_plot_generation, etc.) ...
# ... and your NWS alert task (check_weather_alerts_and_send_pushes from subscriptions/tasks.py if you moved it here) ...


def fetch_and_process_nexrad_level2(radar_site_id="KTLX", specific_s3_file_key=None):
    """
    Fetches a NEXRAD Level 2 file from AWS S3, decompresses it, 
    and performs initial processing with Py-ART.
    """
    print(f"[{datetime.now(timezone.utc).isoformat()}] TASK_NEXRAD_L2: Starting for site {radar_site_id}.")

    # Configure Boto3 S3 client for public access to noaa-nexrad-level2
    # For downloading public data, explicit credentials are often not needed.
    # Using UNSIGNED config tells boto3 not to look for credentials for this specific call.
    s3 = boto3.client('s3', config=BotoConfig(signature_version=UNSIGNED))
    bucket_name = 'noaa-nexrad-level2'

    # Determine the S3 file key to download
    # This logic needs to be robust to find the LATEST file for a given site
    # For now, we'll use a placeholder or allow a specific key to be passed for testing.
    if not specific_s3_file_key:
        # TODO: Implement logic to find the latest S3 key for the radar_site_id
        # This usually involves listing bucket contents by prefix:
        # e.g., s3.list_objects_v2(Bucket=bucket_name, Prefix=f"{datetime.now(timezone.utc).strftime('%Y/%m/%d')}/{radar_site_id}/")
        # and then parsing filenames to find the most recent.
        # This can be complex due to scan times and file availability.
        # For this example, we'll use a fixed placeholder key if none is provided.
        # PLEASE REPLACE THIS WITH ACTUAL LOGIC TO FIND THE LATEST FILE.
        print(f"TASK_NEXRAD_L2_WARNING: specific_s3_file_key not provided. Using a fixed example (likely outdated).")
        # Use a known recent file for testing if you have one, otherwise this will fail.
        # This example is for KTLX on May 31, 2025 at a specific time.
        # You would need to find a current valid S3 key from the noaa-nexrad-level2 bucket.
        # Example structure: YYYY/MM/DD/SITE/SITEYYYYMMDD_HHMMSS_V06.gz
        # Let's form a recent-ish hypothetical key for KTLX
        now_utc = datetime.now(timezone.utc)
        s3_file_key = f"{now_utc.strftime('%Y/%m/%d')}/{radar_site_id.upper()}/{radar_site_id.upper()}{now_utc.strftime('%Y%m%d_%H%M%S')}_V06.gz" # This exact file likely WONT exist
        print(f"TASK_NEXRAD_L2_INFO: Hypothetical S3 key generated (needs real logic): {s3_file_key}")
        # For a real test, find an actual recent file key from: https://noaa-nexrad-level2.s3.amazonaws.com/index.html

        # For initial testing, you might hardcode a known existing S3 key:
        # s3_file_key = "2023/01/01/KTLX/KTLX20230101_000232_V06.gz" # A specific past file
        print(f"TASK_NEXRAD_L2_ERROR: Dynamic latest file key logic not implemented. Cannot proceed without a valid key.")
        return # Exit if we don't have a valid key finding mechanism yet

    # Define local paths for download and decompression
    # Use a temporary directory or a dedicated processing directory
    # Ensure this directory exists and is writable by the user running the Q cluster
    processing_dir = os.path.join(settings.MEDIA_ROOT, 'radar_processing_temp') 
    os.makedirs(processing_dir, exist_ok=True)
    
    base_filename = os.path.basename(s3_file_key)
    local_gz_filename = os.path.join(processing_dir, base_filename)
    local_decompressed_filename = local_gz_filename[:-3] # Remove .gz
################################################################################

    if not specific_s3_file_key:
        print(f"TASK_NEXRAD_L2_INFO: No specific_s3_file_key provided. Attempting to find latest for {radar_site_id}.")
        s3_file_key = None
        try:
            # Look for files in the last ~15-20 minutes.
            # NEXRAD scans are typically every 4-10 minutes.
            # We might need to check the current hour and the previous hour.
            possible_files = []
            for i in range(3): # Check current minute and up to ~15-20 mins ago (3 * 5 min intervals)
                # Note: NWS data is in UTC.
                # This logic might need to span across hour/day boundaries carefully.
                # A more robust way is to list for the current day/hour prefix and then sort.
                
                # Simplified: List objects for the current day and radar site
                now_utc = datetime.now(timezone.utc) - timedelta(minutes=i*5) # Go back in 5-min intervals
                s3_prefix = f"{now_utc.strftime('%Y/%m/%d')}/{radar_site_id.upper()}/"
                
                print(f"TASK_NEXRAD_L2_DEBUG: Listing S3 objects with prefix: {s3_prefix}")
                response = s3.list_objects_v2(Bucket=bucket_name, Prefix=s3_prefix, RequestPayer='requester')
                
                if 'Contents' in response:
                    for obj in response['Contents']:
                        filename = obj['Key']
                        # Example filename: KTLX20250531_221500_V06 or KTLX20250531_221500_V06.gz
                        if radar_site_id.upper() in filename and ("_V06" in filename or "_HD0" in filename): # V06 is common for L2, HD0 for some TDWR
                            # Extract timestamp from filename (this needs to be robust)
                            # KTLX20250531_221500_V06 -> timestamp part 20250531_221500
                            try:
                                parts = os.path.basename(filename).split('_')
                                if len(parts) >= 2:
                                    timestamp_str = parts[0][len(radar_site_id):] + "_" + parts[1] # e.g., 20250531_221500
                                    file_dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
                                    possible_files.append({'key': filename, 'timestamp': file_dt, 'size': obj['Size']})
                            except ValueError:
                                print(f"TASK_NEXRAD_L2_DEBUG: Could not parse timestamp from {filename}")
                                continue
            
            if possible_files:
                # Sort by timestamp, newest first
                possible_files.sort(key=lambda x: x['timestamp'], reverse=True)
                # Filter out very small files which might be incomplete or metadata
                # A typical L2 volume file is several MB. Let's say > 1MB.
                valid_files = [f for f in possible_files if f['size'] > 1000000] 
                if valid_files:
                    s3_file_key = valid_files[0]['key']
                    print(f"TASK_NEXRAD_L2_INFO: Found latest file: {s3_file_key} (Timestamp: {valid_files[0]['timestamp']})")
                else:
                    print(f"TASK_NEXRAD_L2_WARNING: No sufficiently large files found in recent scans for {radar_site_id}.")
            else:
                print(f"TASK_NEXRAD_L2_WARNING: No files found in recent scans for {radar_site_id}.")

        except Exception as e_list:
            print(f"TASK_NEXRAD_L2_ERROR: Error listing S3 bucket for latest file: {e_list}")
            traceback.print_exc()

        if not s3_file_key:
            print(f"TASK_NEXRAD_L2_ERROR: Could not determine latest S3 file key for {radar_site_id}. Task cannot proceed.")
            return # Exit if no file key found


################################################################################
    print(f"TASK_NEXRAD_L2: Attempting to download {s3_file_key} from bucket {bucket_name} to {local_gz_filename}")

    try:
        s3.download_file(bucket_name, s3_file_key, local_gz_filename)
        print(f"TASK_NEXRAD_L2: Successfully downloaded {local_gz_filename}")

        # Decompress the .gz file
        print(f"TASK_NEXRAD_L2: Decompressing {local_gz_filename} to {local_decompressed_filename}...")
        with gzip.open(local_gz_filename, 'rb') as f_in:
            with open(local_decompressed_filename, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        print(f"TASK_NEXRAD_L2: Decompressed to {local_decompressed_filename}")
        os.remove(local_gz_filename) # Clean up the .gz file

        # --- Process with Py-ART ---
        print(f"TASK_NEXRAD_L2: Reading radar data with Py-ART from {local_decompressed_filename}...")
        try:
            radar = pyart.io.read(local_decompressed_filename) # Py-ART's universal read function
            print(f"TASK_NEXRAD_L2: Successfully read radar data. Radar info: {radar.info()}")
            print(f"TASK_NEXRAD_L2: Available fields: {list(radar.fields.keys())}")

            # Example: Get basic reflectivity (common field name 'reflectivity')
            if 'reflectivity' in radar.fields:
                reflectivity_data = radar.fields['reflectivity']['data']
                print(f"TASK_NEXRAD_L2: Reflectivity field shape: {reflectivity_data.shape}")
                # TODO: From here, you would:
                # 1. Extract other desired moments (velocity, ZDR, CC, etc.)
                # 2. Perform any necessary corrections or QC.
                # 3. Grid the data (e.g., using pyart.map.grid_from_radars).
                # 4. Generate an image using pyart.graph.RadarDisplay or GridMapDisplay.
                #    - This involves setting projections, colormaps, bounds.
                #    - display.plot_ppi_map('reflectivity', ...)
                #    - plt.savefig(...)
                # 5. Determine the geographic bounds of the generated image.
                # 6. Save image path and bounds to database or cache for frontend to access.
                print("TASK_NEXRAD_L2: Placeholder for further processing (gridding, plotting, saving image & bounds).")
            else:
                print(f"TASK_NEXRAD_L2_WARNING: 'reflectivity' field not found in radar object. Available fields: {list(radar.fields.keys())}")

        except Exception as e_pyart:
            print(f"TASK_NEXRAD_L2_ERROR: Py-ART processing failed: {e_pyart}")
            traceback.print_exc()
        finally:
            # Clean up the decompressed file
            if os.path.exists(local_decompressed_filename):
                os.remove(local_decompressed_filename)
                print(f"TASK_NEXRAD_L2: Cleaned up {local_decompressed_filename}")

    except Exception as e:
        print(f"TASK_NEXRAD_L2_ERROR: Failed to download or process {s3_file_key}: {e}")
        traceback.print_exc()

    print(f"[{datetime.now(timezone.utc).isoformat()}] TASK_NEXRAD_L2: Finished for site {radar_site_id}.")
