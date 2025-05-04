from django.db import models
from django.conf import settings

class Plan(models.Model):
    name = models.CharField(max_length=100, unique=True) # e.g., "Free", "Premium Monthly"
    stripe_price_id = models.CharField(max_length=100, unique=True,
                                       help_text="Stripe Price ID (e.g., price_ H5ggL5LP...)")
    price = models.DecimalField(max_digits=6, decimal_places=2, default=0.00,
                                help_text="Display price (e.g., 5.00)")
    features = models.TextField(blank=True, help_text="Optional description of features")

    def __str__(self):
        return self.name

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
