from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from push_notifications.models import WebPushDevice
import json


User = get_user_model()

class Command(BaseCommand):
    help = 'Sends a test push notification to a specified user.'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='The username of the user to send the push to.')
        parser.add_argument('--title', type=str, default='Test Push!', help='Notification title.')
        parser.add_argument('--body', type=str, default='This is a test notification from Django.', help='Notification body.')
        parser.add_argument('--url', type=str, default='/', help='URL to open on notification click.')


    def handle(self, *args, **options):
        username = options['username']
        title = options['title']
        body = options['body']
        url = options['url']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist.')

        # Find active WebPushDevice(s) for the user
        # Note: send_message can be called on a queryset
        devices = WebPushDevice.objects.filter(user=user, active=True)

        if not devices.exists():
            self.stdout.write(self.style.WARNING(f'No active push devices found for user "{username}".'))
            return

        payload = {
            "head": title, # Or "title" depending on your SW
            "body": body,
            "icon": "/static/images/icons/Icon_192.jpg", # Make sure this path is correct
            "url": url # URL to open on click
        }

        self.stdout.write(f"Attempting to send push notification to {devices.count()} device(s) for user '{username}'...")
        self.stdout.write(f"Payload: {json.dumps(payload)}")

        # Send the push notification
        # The send_message method on the queryset handles sending to all devices
        # It expects a string or a dict for the message argument.
        # If dict, it will be json.dumps'd.
        # `extra` kwargs are passed to webpush() call.
        try:
            devices.send_message(body)
#           devices.send_message(payload) # Pass the dict directly
            self.stdout.write(self.style.SUCCESS(f'Successfully sent push notification command for user "{username}".'))
#            self.stdout.write(self.style.NOTICE('Check device and service worker console for receipt.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error sending push notification: {e}'))
            import traceback
            traceback.print_exc()
