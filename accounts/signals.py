from django.db.models.signals import post_save
from django.conf import settings # Use settings.AUTH_USER_MODEL
from django.dispatch import receiver
from .models import Profile
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth import get_user_model

User = get_user_model()



# This function will run *after* a User object is saved
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    # 'created' is True if a new User record was created
    if created:
        Profile.objects.create(user=instance)

# Optional: ensure profile is saved when user is saved (might be redundant depending on use case)
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    # instance refers to the User object
    # access the related profile via the reverse relationship 'profile'
    instance.profile.save()

@receiver(post_save, sender=User) # Connects this function to the post_save signal for the User model
def send_welcome_email_on_user_creation(sender, instance, created, **kwargs):
    """
    Sends a welcome email when a new User instance is created.
    """
    if created: # Only run if a new record was created (not on updates)
        user = instance
        print(f"SIGNAL: New user created: {user.username}, email: {user.email}. Attempting to send welcome email.")

        # Prepare context for email templates
        # 'site_name' can be pulled from settings or Django Sites framework
        # For simplicity, let's assume you might add SITE_NAME to settings.py
        site_name = getattr(settings, 'SITE_NAME_DISPLAY', 'Unfortunate Neighbor App') # Add SITE_NAME_DISPLAY to settings.py
        
        context = {
            'user': user,
            'protocol': 'https' if not settings.DEBUG else 'http', # Or from settings.SITE_SCHEME
            'domain': settings.SITE_DOMAIN.replace('https://','').replace('http://',''), # Assumes SITE_DOMAIN is in settings
            'site_name': site_name,
        }

        subject = render_to_string('accounts/email/welcome_email_subject.txt', context).strip()
        html_message = render_to_string('accounts/email/welcome_email_body.html', context)
        plain_message = render_to_string('accounts/email/welcome_email_body.txt', context)
        # Or, if you don't have a separate .txt body template:
        # plain_message = strip_tags(html_message) 

        from_email = settings.DEFAULT_FROM_EMAIL # e.g., "no-reply@unfortunateneighbor.com"
        
        if user.email: # Only send if the user has an email address
            try:
                send_mail(
                    subject,
                    plain_message,
                    from_email,
                    [user.email], # Must be a list
                    html_message=html_message,
                    fail_silently=False
                )
                print(f"SIGNAL: Welcome email successfully sent/queued for {user.email} via {settings.EMAIL_BACKEND}.")
            except Exception as e:
                print(f"SIGNAL: Error sending welcome email to {user.email}: {e}")
                # In production, you should log this error properly using Django's logging
                # import logging
                # logger = logging.getLogger(__name__)
                # logger.error(f"Error sending welcome email to {user.email}: {e}", exc_info=True)
        else:
            print(f"SIGNAL: User {user.username} was created without an email address. No welcome email sent.")
