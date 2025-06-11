# subscriptions/management/commands/send_test_email.py
from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail
from django.conf import settings
import traceback

class Command(BaseCommand):
    help = 'Sends a test email using the current Django email settings (e.g., Amazon SES) to a specified recipient.'

    def add_arguments(self, parser):
        # Define an argument for the recipient's email address
        parser.add_argument(
            'recipient_email', 
            type=str, 
            help='The email address to send the test email to. If using SES sandbox, this address must be verified in SES.'
        )

    def handle(self, *args, **options):
        recipient_email = options['recipient_email']

        subject = 'Test Email from Django App via Amazon SES (Management Command)'
        message_body = (
            f'Hello!\n\n'
            f'This is a test email sent to {recipient_email} from your Django application '
            f'using the email settings configured in settings.py (currently targeting {settings.EMAIL_HOST}).\n\n'
            f'If you received this, your email sending setup is working for this recipient from this sender.\n\n'
            f'Regards,\nYour Weather App'
        )

        # This will use the DEFAULT_FROM_EMAIL from your settings.py
        from_email = settings.DEFAULT_FROM_EMAIL 

        self.stdout.write(f"Attempting to send test email from: {from_email}")
        self.stdout.write(f"Attempting to send test email to: {recipient_email}")
        self.stdout.write(f"Using EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
        self.stdout.write(f"Using EMAIL_HOST: {settings.EMAIL_HOST}")

        try:
            num_sent = send_mail(
                subject,
                message_body,
                from_email,
                [recipient_email], # Must be a list or tuple
                fail_silently=False # Raise an exception on error
            )
            if num_sent > 0:
                self.stdout.write(self.style.SUCCESS(f"SUCCESS: Email reported as sent to {recipient_email} via SES (or configured backend)."))
                self.stdout.write(self.style.SUCCESS("Please check the recipient's inbox (and spam folder). Also monitor SES sending statistics if applicable."))
            else:
                self.stdout.write(self.style.WARNING("INFO: send_mail returned 0. This might indicate the email was not actually sent by the backend, even though no exception was raised."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"ERROR SENDING EMAIL: {e}"))
            self.stderr.write(traceback.format_exc())
            # Optional: raise CommandError to indicate failure to the shell
            # raise CommandError(f"Failed to send email: {e}")
