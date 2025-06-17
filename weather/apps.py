# weather/apps.py
from django.apps import AppConfig
from django.utils import timezone 
from datetime import timedelta    

class WeatherConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'weather'

    def ready(self):
        # By removing the schedule creation logic from here,
        # the Django Admin becomes the only source of truth for schedules.
        print("WeatherConfig.ready() called. Automatic scheduling is now disabled.")
        pass