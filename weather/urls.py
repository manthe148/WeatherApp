from django.urls import path
from . import views # Import views from the weather app

app_name = 'weather' # Namespace for weather app URLs

urlpatterns = [
    # When the URL matches the base path where this is included (e.g., /weather/),
    # call the get_weather_alerts view function.
    # Name this pattern 'alert_list' for potential use with {% url %} later.
    path('', views.get_weather_alerts, name='weather_page'),
    path('radar/premium/', views.premium_radar_view, name='premium_radar'),
    path('models/', views.weather_models_landing_view, name='weather_models_landing'),
    path('api/gfs-temperature-image-info/', views.get_gfs_temperature_image_info, name='api_gfs_temperature_image_info'),
    path('models/gfs-temperature/', views.gfs_temperature_model_view, name='gfs_temperature_model_view'), # Renamed
    # New landing page for models
]
