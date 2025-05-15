# weather/management/commands/generate_model_plot.py
from django.core.management.base import BaseCommand
from weather.grib_processing import get_latest_gfs_rundate_and_hour, generate_gfs_plot_for_hour # IMPORT NEW FUNCTIONS

class Command(BaseCommand):
    help = 'Generates a GFS model plot for a specified forecast hour.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fhr', type=str, default='006',
            help='Forecast hour string (e.g., "006", "012", "024"). Must be 3 digits.'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Manually generating single GFS model plot..."))

        run_date_str, model_run_hour_str = get_latest_gfs_rundate_and_hour(self.stdout.write)
        forecast_hour_str = options['fhr']

        # Ensure forecast_hour_str is 3 digits
        try:
            fhr_int = int(forecast_hour_str)
            forecast_hour_str = f"{fhr_int:03d}"
        except ValueError:
            self.stderr.write(self.style.ERROR(f"Invalid forecast hour: '{options['fhr']}'. Using '006'."))
            forecast_hour_str = "006"

        self.stdout.write(f"Attempting to generate plot for Run: {run_date_str} {model_run_hour_str}Z, Forecast: F{forecast_hour_str}")

        success, image_path = generate_gfs_plot_for_hour(
            run_date_str,
            model_run_hour_str,
            forecast_hour_str,
            self.stdout.write # Pass the command's output function
        )

        if success:
            self.stdout.write(self.style.SUCCESS(f"Successfully generated plot: {image_path}"))
        else:
            self.stdout.write(self.style.ERROR("Failed to generate plot. Check logs above."))
