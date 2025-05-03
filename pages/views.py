from django.shortcuts import render

# Create your views here.
# View for the Homepage
def home_view(request):
    # We'll create 'pages/home.html' later
    return render(request, 'pages/home.html')

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
