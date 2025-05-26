# weather/context_processors.py
from .utils import get_user_navbar_alert_info # Assuming utils.py is in the same app (weather)

def navbar_alerts_processor(request):
    """
    Makes alert information available to all templates for the navbar.
    """
    alert_info = {'status': None, 'count': 0} # Default structure for anonymous users
    if request.user.is_authenticated:
        alert_info = get_user_navbar_alert_info(request.user)
    
    return {'navbar_alert_info': alert_info}
