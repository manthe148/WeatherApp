from django.db import models
from django.conf import settings
from accounts.models import SavedLocation # Assuming SavedLocation is in accounts.models



class Plan(models.Model):
    BILLING_INTERVAL_CHOICES = [
        ('month', 'Monthly'),
        ('year', 'Yearly'),
    ]

    name = models.CharField(max_length=100, unique=True) # e.g., "Premium Monthly", "Premium Yearly"
    stripe_price_id = models.CharField(
        max_length=100, unique=True,
        help_text="Stripe Price ID (e.g., price_H5ggL5LP...)"
    )
    price = models.DecimalField(
        max_digits=6, decimal_places=2, default=0.00,
        help_text="Display price (e.g., 5.00 for this interval)"
    )
    billing_interval = models.CharField(
        max_length=10,
        choices=BILLING_INTERVAL_CHOICES,
        default='month',
        help_text="The billing frequency (e.g., month or year)"
    )
    tier_name = models.CharField(
        max_length=50,
        default="Default", # e.g., "Basic", "Premium", "Pro"
        help_text="A common name for this plan tier (e.g., 'Premium') to group monthly/yearly versions."
    )
    features = models.TextField(
        blank=True, 
        help_text="Optional description of features (use line breaks for bullets)"
    )
    display_order = models.IntegerField(
        default=0,
        help_text="Order in which to display plan tiers (lower numbers first)"
    )

    def __str__(self):
        return f"{self.tier_name} - {self.name} ({self.get_billing_interval_display()})"

    class Meta:
        ordering = ['display_order', 'tier_name', 'billing_interval']

class Subscription(models.Model):
    # Possible subscription statuses from Stripe
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('trialing', 'Trialing'),
        ('incomplete', 'Incomplete'),
        ('incomplete_expired', 'Incomplete Expired'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('unpaid', 'Unpaid'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="subscription") # One subscription per user
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True,
                             help_text="The Plan the user is subscribed to")
    stripe_subscription_id = models.CharField(max_length=100, unique=True,
                                              help_text="Stripe Subscription ID (e.g., sub_...)")
    stripe_customer_id = models.CharField(max_length=100, unique=True,
                                           help_text="Stripe Customer ID (e.g., cus_...)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='incomplete')
    current_period_end = models.DateTimeField(null=True, blank=True,
                                           help_text="End date of the current billing cycle")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        plan_name = self.plan.name if self.plan else "No Plan"
        return f"{self.user.username} - {plan_name} ({self.status})"

    def is_active(self):
        # Helper property to check if subscription is considered active for features
        return self.status in ['active', 'trialing']


class NotifiedAlert(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # Store the unique ID provided by the NWS for each alert
    nws_alert_id = models.CharField(max_length=255, db_index=True)
    # Optionally link to the specific saved location this alert was for
    saved_location = models.ForeignKey(SavedLocation, on_delete=models.CASCADE, null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ensure we don't notify the same user about the same NWS alert ID multiple times
        unique_together = [['user', 'nws_alert_id']]
        ordering = ['-sent_at']

    def __str__(self):
        return f"Alert {self.nws_alert_id} sent to {self.user.username} at {self.sent_at}"
