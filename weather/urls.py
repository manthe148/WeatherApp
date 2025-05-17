# weather/urls.py (YOUR CURRENT FILE)
from django.urls import path
from . import views

app_name = 'weather'

urlpatterns = [
    path('', views.get_weather_alerts, name='weather_page'),
    path('radar/premium/', views.premium_radar_view, name='premium_radar'),

    # Page for displaying GFS models (Temp, CAPE, etc.)
    # This is currently your main models page, let's use this for the multi-parameter GFS display
    path('models/', views.weather_models_view, name='weather_models'),

    # API endpoint for GFS model image data
    # This API will serve the data for the /models/ page
    path('api/model-image-data/', views.get_model_image_api_data, name='api_model_image_data'),

    # GFS Parameter Display Page - This one is redundant if /models/ is your GFS page
    # path('models/gfs/', views.gfs_model_page_view, name='gfs_model_page'), # LET'S REMOVE THIS FOR SIMPLICITY
]
