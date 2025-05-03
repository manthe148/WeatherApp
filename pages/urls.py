from django.urls import path
from . import views # Import views from the pages app

app_name = 'pages' # Namespace

urlpatterns = [
    # Map the app's root URL ('') to home_view, name it 'home'
    path('', views.home_view, name='home'),
    # Map the URL 'about/' to about_view, name it 'about'
    path('about/', views.about_view, name='about'),
]
