from django.urls import path
from . import views # Import views from the weather app

app_name = 'weather' # Namespace for weather app URLs

urlpatterns = [
    # When the URL matches the base path where this is included (e.g., /weather/),
    # call the get_weather_alerts view function.
    # Name this pattern 'alert_list' for potential use with {% url %} later.
    path('', views.get_weather_alerts, name='alert_list'),
    # Add other weather-related URLs here later (e.g., radar, forecast)
    path('radar/premium/', views.premium_radar_view, name='premium_radar')

]
