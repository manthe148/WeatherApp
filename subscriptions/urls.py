from django.urls import path
from . import views

from .views import (
    subscription_plan_view,
    create_checkout_session_view,
    SubscriptionSuccessView, # Should match class name in views.py
    SubscriptionCancelView,  # Should match class name in views.py
    stripe_webhook_view,
    save_push_subscription_view
)

app_name = 'subscriptions' # Define namespace

urlpatterns = [
    # URL for displaying the plans
    path('plans/', views.subscription_plan_view, name='plan_selection'),
    # URL for handling the POST request to create a Stripe session
    path('create-checkout-session/', views.create_checkout_session_view, name='create_checkout_session'),
    # We'll add URLs for success/cancel pages later
    path('checkout/success/', SubscriptionSuccessView.as_view(), name='success'),
    path('checkout/cancel/', SubscriptionCancelView.as_view(), name='cancel'),
    path('webhook/', stripe_webhook_view, name='stripe_webhook'),
    path('save-push-subscription/', save_push_subscription_view, name='save_push_subscription'),
]
