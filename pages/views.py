# pages/views.py

from django.shortcuts import render
from subscriptions.models import NotifiedAlert

# Create your views here.
# View for the Homepage
def home_view(request):
    # Count all instances where a notification has been recorded
    notification_count = NotifiedAlert.objects.count()

    # You can add any other context your homepage might need here
    # For example, fetching a few recent model plots or highlighted features

    context = {
        'notification_count': notification_count,
        # ... other context variables ...
    }
    return render(request, 'pages/home.html', context) # Adjust 'pages/home.html' if needed
# View for the Weather page
def weather_view(request):
    # We'll create 'pages/weather.html' later
    # In the future, this view might fetch actual weather data
    # and pass it to the template in a context dictionary.
    context = {} # Empty context for now
    return render(request, 'pages/weather.html', context)

# View for the About page
def about_view(request):
    # We'll create 'pages/about.html' later
    return render(request, 'pages/about.html')
