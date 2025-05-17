# weather/urls.py
from django.urls import path
from . import views

app_name = 'weather'

urlpatterns = [
    path('', views.get_weather_alerts, name='weather_page'), # This will become the "Alerts" page later
    path('radar/premium/', views.premium_radar_view, name='premium_radar'),

    # 1. Weather Models Landing Page (for selecting GFS, NAM, etc.)
    path('models/', views.weather_models_landing_view, name='weather_models_landing'),

    # 2. Page for displaying specific GFS model parameters (Temp, CAPE, etc.)
    path('models/gfs/', views.gfs_model_page_view, name='gfs_model_page'),

    # 3. API endpoint for fetching data for the GFS parameter page
    path('api/gfs-model-data/', views.get_gfs_model_api_data, name='api_gfs_model_data'),
]
