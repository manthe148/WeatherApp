# pages/middleware.py
from django.contrib import messages
from .models import SiteAnnouncement
# Assuming Profile is in accounts.models. If it's in a different app, adjust import.
# from accounts.models import Profile # Not strictly needed here if accessing via request.user.profile

class SiteAnnouncementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Initialize our custom attribute on the request object
        request.site_announcement_to_display = None # Default to no announcement

        if request.user.is_authenticated and hasattr(request.user, 'profile'):
            # Fetch the latest active announcement (you could fetch all active and unseen if you want a queue)
            latest_active_announcement = SiteAnnouncement.objects.filter(is_active=True).order_by('-created_at').first()

            if latest_active_announcement:
                profile = request.user.profile

                # Ensure seen_announcement_identifiers is a list
                if not isinstance(profile.seen_announcement_identifiers, list):
                    profile.seen_announcement_identifiers = []

                if latest_active_announcement.unique_identifier not in profile.seen_announcement_identifiers:
                    # This is a new announcement for this user
                    request.site_announcement_to_display = latest_active_announcement # Add to request

                    # Mark as seen
                    profile.seen_announcement_identifiers.append(latest_active_announcement.unique_identifier)
                    profile.save(update_fields=['seen_announcement_identifiers'])

        response = self.get_response(request)
        return response
