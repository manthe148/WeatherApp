"""
URL configuration for weather_site project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from accounts import views as accounts_views # Import accounts views
from accounts.views import ServiceWorkerView
from django.views.generic import TemplateView
from django.conf import settings # Add this
from django.conf.urls.static import static # Add this





urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('pages.urls')), # It's good practice to add namespaces here later if not already
    path('weather/', include('weather.urls', namespace='weather')), # Added namespace='weather' for good practice

    # For your custom account views (like signup, profile if defined in accounts.urls)
    # It's good if accounts.urls defines an app_name = 'accounts'
    path('accounts/', include('accounts.urls')), 
    
    # For Django's built-in auth views (login, logout, password_reset, etc.)
    # This will make URLs like /accounts/login/, /accounts/password_reset/ available
    # with names 'login', 'password_reset', etc.
    path('accounts/', include('django.contrib.auth.urls')), # <<< ADD THIS LINE

    # The line below for signup might be redundant if 'accounts.urls' already handles 'signup/'
    # path('accounts/signup/', accounts_views.sign_up, name='signup'), 
    # It's often cleaner to have all '/accounts/...' routes originate from one of the 'accounts/' includes.
    # For now, let's leave it, but if 'accounts.urls' also has a signup, Django uses the first match.

    path('subscriptions/', include('subscriptions.urls', namespace='subscriptions')), # Added namespace
    
    path('sw.js', ServiceWorkerView.as_view(), name='service_worker'),
    path('offline/', TemplateView.as_view(template_name="offline.html"), name='offline_page'),
]



if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


