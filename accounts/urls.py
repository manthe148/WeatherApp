from django.urls import path, include
from . import views # Import views from the accounts app
from django.contrib.auth import views as auth_views


app_name = 'accounts' # Define the namespace

urlpatterns = [
    path('signup/', views.sign_up, name='signup'),
    # Add path for settings view (view function will be created next)
    path('settings/', views.user_settings_view, name='settings'),

    # Explicitly define login using the built-in view
    # This ensures 'accounts:login' definitely works
    path(
        'login/',
        auth_views.LoginView.as_view(template_name='registration/login.html'),
        name='login'
    ),

    # Manual definition for Logout using Django's LogoutView
    # LOGOUT_REDIRECT_URL in settings.py handles the redirect destination
    path(
        'logout/',
        auth_views.LogoutView.as_view(),
        name='logout'
    ),

    # Include built-in auth URLs (login, logout, password_reset, etc.)
    # These URLs won't use the 'accounts' namespace automatically
    # but rely on global names like 'login', 'logout'.
    path('', include('django.contrib.auth.urls')),
]
