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

urlpatterns = [
    path('admin/', admin.site.urls),
    # You might have other path() entries here later
    path('', include('pages.urls')),
    path('weather/', include('weather.urls')),
    path('accounts/', include('accounts.urls')),
    path('accounts/signup/', accounts_views.sign_up, name='signup'),
   path('subscriptions/', include('subscriptions.urls')),
    path('sw.js', ServiceWorkerView.as_view(), name='service_worker'),
]
