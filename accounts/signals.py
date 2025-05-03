from django.db.models.signals import post_save
from django.conf import settings # Use settings.AUTH_USER_MODEL
from django.dispatch import receiver
from .models import Profile

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
