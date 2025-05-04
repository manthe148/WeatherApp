# --- Ensure ALL these imports are present at the TOP ---
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings
from .models import Plan, Subscription
from django.views.generic import TemplateView
import stripe
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseServerError, JsonResponse
from django.contrib.auth import get_user_model
from django.contrib import messages
from decimal import Decimal, InvalidOperation # Keep if settings view is in this file
from datetime import datetime, timezone # Moved to top
import traceback # ADDED import
import json # Keep just in case
from push_notifications.models import WebPushDevice # The model to store subscription

# --- End Imports ---


# Add other imports from previous steps if needed (like messages, geopy etc for other views)

class SubscriptionSuccessView(TemplateView):
    template_name = 'subscriptions/success.html'

class SubscriptionCancelView(TemplateView):
    template_name = 'subscriptions/cancel.html'

@login_required
def subscription_plan_view(request):
    # Fetch all available plans from your database
    # You might want to filter this later (e.g., exclude a "Free" plan)
    plans = Plan.objects.all().order_by('price') # Order by price

    context = {
        'plans': plans,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY
    }
    return render(request, 'subscriptions/plan_selection.html', context)

# Add this function back into subscriptions/views.py

@require_POST
@login_required
def create_checkout_session_view(request):
    price_id = request.POST.get('price_id')
    if not price_id:
        messages.error(request, "No subscription plan selected.")
        return redirect('subscriptions:plan_selection')

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        success_url = request.build_absolute_uri(
            reverse('subscriptions:success')
        ) + '?session_id={CHECKOUT_SESSION_ID}'
        cancel_url = request.build_absolute_uri(
            reverse('subscriptions:cancel')
        )
    except Exception as e:
        messages.error(request, f"Error building redirect URLs: {e}")
        return redirect('subscriptions:plan_selection')

    # --- Prepare parameters for Stripe Session ---
    session_params = {
        'line_items': [{
            'price': price_id,
            'quantity': 1,
        }],
        'mode': 'subscription',
        'success_url': success_url,
        'cancel_url': cancel_url,
        'client_reference_id': request.user.id,
        'payment_method_types': ['card'], # Good to be explicit
    }

    # --- Conditionally add customer_email ---
    if request.user.email:
        session_params['customer_email'] = request.user.email
    # --- End conditional email ---

    try:
        # Create the session using the prepared parameters dictionary
        checkout_session = stripe.checkout.Session.create(**session_params) # Use ** to unpack dict

        return redirect(checkout_session.url, status=303)

    except stripe.error.StripeError as e:
        messages.error(request, f"Error communicating with Stripe: {e}")
        print(f"Stripe Error: {e}")
        return redirect('subscriptions:plan_selection')
    except Exception as e:
        messages.error(request, f"An unexpected error occurred: {e}")
        print(f"Checkout Error: {e}")
        traceback.print_exc() # Keep traceback for debugging
        return redirect('subscriptions:plan_selection')

# --- End of create_checkout_session_view function ---

# Make sure stripe_webhook_view and other views/classes are still present below this

# --- CORRECTED Webhook View ---
@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    """Listens for events from Stripe."""
    payload = request.body
    sig_header = request.headers.get('stripe-signature')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    event = None

    # Verification Try/Except Block
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
        print(f"Webhook received: Event ID: {event.id}, Type: {event.type}")
    except ValueError as e:
        print(f"Webhook error parsing payload: {e}")
        return HttpResponseBadRequest("Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        print(f"Webhook signature verification failed: {e}")
        return HttpResponseBadRequest("Invalid signature")
    except Exception as e: # Catch any other construction errors
        print(f"Webhook construction error: {e}")
        traceback.print_exc() # Print traceback for construction errors too
        return HttpResponseBadRequest(f"Webhook construction error: {e}")

    # --- Handle the checkout.session.completed event ---
    if event.type == 'checkout.session.completed':
        session = event.data.object
        print(f"Processing checkout.session.completed for session {session.id}")

        client_reference_id = session.get('client_reference_id')
        stripe_customer_id = session.get('customer')
        stripe_subscription_id = session.get('subscription')

        if client_reference_id is None:
            print("Webhook error: client_reference_id missing in checkout session.")
            return HttpResponseBadRequest("Missing client_reference_id.")

        User = get_user_model()
        try:
            user = User.objects.get(id=client_reference_id)
            print(f"Found user: {user.username}")

            if stripe_subscription_id:
                # --- Inner Try/Except for Stripe API calls and DB operations ---
                try:
                    print(f"Attempting to retrieve Stripe Subscription ID: {stripe_subscription_id}")
                    stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
                    print(f"Retrieved Stripe Subscription. Status: {stripe_sub.status}")

                    stripe_price_id = stripe_sub.plan.id
                    period_end_timestamp = stripe_sub.get('current_period_end') # Use .get() for safety
                    print(f"Stripe Subscription Period End Timestamp: {period_end_timestamp}")

                    current_period_end_dt = None
                    if period_end_timestamp is not None:
                        try:
                            current_period_end_dt = datetime.fromtimestamp(period_end_timestamp, tz=timezone.utc)
                            print(f"Converted Period End Datetime: {current_period_end_dt}")
                        except Exception as e_conv:
                            print(f"!!! ERROR converting timestamp {period_end_timestamp}: {e_conv}")

                    # Find Plan in DB
                    try:
                        plan = Plan.objects.get(stripe_price_id=stripe_price_id)
                        print(f"Found plan in DB: {plan.name}")

                        # Update/Create Subscription in DB
                        subscription, created = Subscription.objects.update_or_create(
                            user=user,
                            defaults={
                                'plan': plan,
                                'stripe_subscription_id': stripe_subscription_id,
                                'stripe_customer_id': stripe_customer_id,
                                'status': stripe_sub.status,
                                'current_period_end': current_period_end_dt,
                            }
                        )
                        if created:
                            print(f"CREATED Subscription DB record for user {user.username}")
                        else:
                            print(f"UPDATED Subscription DB record for user {user.username}")

                    except Plan.DoesNotExist:
                        print(f"!!! Webhook error: Plan with Stripe Price ID {stripe_price_id} not found in database.")
                        return HttpResponseServerError("Plan not found in DB.")
                    except Exception as e_db: # Catch DB specific errors
                        print(f"!!! Webhook error saving to DB: {e_db}")
                        traceback.print_exc() # Print DB error traceback
                        return HttpResponseServerError("DB error saving subscription.")

                # Correct placement for StripeError exception
                except stripe.error.StripeError as e_sub:
                    print(f"!!! Webhook error retrieving/processing Stripe Subscription {stripe_subscription_id}: {e_sub}")
                    traceback.print_exc() # Print traceback for Stripe errors
                    return HttpResponseServerError("Stripe API error during subscription processing.")
                # Correct placement for the general exception handler
                except Exception as e_inner:
                    print(f"!!! Webhook error processing subscription inner: {e_inner}")
                    traceback.print_exc() # <--- PRINT TRACEBACK HERE
                    return HttpResponseServerError("Internal server error processing subscription.")
                # --- End Inner Try/Except ---
            else:
                print("!!! Webhook error: stripe_subscription_id missing in checkout session.")
                return HttpResponseBadRequest("Missing subscription ID.")

        except User.DoesNotExist:
            print(f"Webhook error: User with ID {client_reference_id} not found.")
            return HttpResponseBadRequest("User not found.")
        # Let other unexpected errors bubble up if needed during debugging,
        # or add a final broad except Exception here if necessary for production.

    # --- Handle other event types ---
    elif event.type == 'invoice.paid':
        # Continued payment success / Subscription renewed
        invoice = event.data.object
        stripe_subscription_id = invoice.get('subscription')
        print(f"Processing invoice.paid for subscription {stripe_subscription_id}")
        try:
            # Retrieve the full Subscription object from Stripe to get updated period end
            stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
            # Find the local subscription record
            subscription = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)
            # Update status and period end
            subscription.status = stripe_sub.status # Should be 'active'
            if stripe_sub.current_period_end:
                subscription.current_period_end = datetime.fromtimestamp(
                    stripe_sub.current_period_end, tz=timezone.utc
                )
            subscription.save()
            print(f"Updated subscription {stripe_subscription_id} on invoice.paid.")
        except Subscription.DoesNotExist:
            print(f"!!! Error: Subscription {stripe_subscription_id} not found in DB for invoice.paid.")
        except stripe.error.StripeError as e:
            print(f"!!! Stripe Error handling {event.type} for {stripe_subscription_id}: {e}")
        except Exception as e:
            print(f"!!! Error handling {event.type} for {stripe_subscription_id}: {e}")
            traceback.print_exc()

    elif event.type in ['customer.subscription.updated', 'customer.subscription.deleted']:
        # Handles cancellations, plan changes, etc.
        stripe_sub = event.data.object # The subscription object is the event data
        stripe_subscription_id = stripe_sub.id
        print(f"Processing {event.type} for subscription {stripe_subscription_id}")
        try:
            # Find the local subscription record
            subscription = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)
            # Update status and period end from the event data
            subscription.status = stripe_sub.status # e.g., 'canceled', 'active' (if plan changed)
            if stripe_sub.current_period_end:
                 subscription.current_period_end = datetime.fromtimestamp(
                     stripe_sub.current_period_end, tz=timezone.utc
                 )
            elif stripe_sub.status == 'canceled':
                 # If canceled, maybe use cancel_at_period_end timestamp if available?
                 # Or just set period end based on cancellation time? Depends on desired logic.
                 # For simplicity, we might just set status to canceled.
                 if stripe_sub.canceled_at:
                     subscription.current_period_end = datetime.fromtimestamp(
                         stripe_sub.canceled_at, tz=timezone.utc
                     )

            # If plan changed, find new Plan object and update FK (more complex)
            # current_plan_price_id = stripe_sub.plan.id
            # if subscription.plan.stripe_price_id != current_plan_price_id:
            #    try:
            #        new_plan = Plan.objects.get(stripe_price_id=current_plan_price_id)
            #        subscription.plan = new_plan
            #        print(f"Updated plan for subscription {stripe_subscription_id}")
            #    except Plan.DoesNotExist:
            #        print(f"!!! Error: New plan {current_plan_price_id} not found.")

            subscription.save()
            print(f"Updated subscription {stripe_subscription_id} on {event.type}.")

        except Subscription.DoesNotExist:
            print(f"!!! Error: Subscription {stripe_subscription_id} not found in DB for {event.type}.")
        except Exception as e:
            print(f"!!! Error handling {event.type} for {stripe_subscription_id}: {e}")
            traceback.print_exc()

    elif event.type == 'invoice.payment_failed':
        # Handle failed payments (update status)
        invoice = event.data.object
        stripe_subscription_id = invoice.get('subscription')
        print(f"Processing invoice.payment_failed for subscription {stripe_subscription_id}")
        try:
            subscription = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)
            subscription.status = 'past_due' # Or 'unpaid' depending on Stripe settings/logic
            subscription.save()
            print(f"Set status to '{subscription.status}' for subscription {stripe_subscription_id} due to payment failure.")
        except Subscription.DoesNotExist:
             print(f"!!! Error: Subscription {stripe_subscription_id} not found in DB for {event.type}.")
        except Exception as e:
             print(f"!!! Error handling {event.type} for {stripe_subscription_id}: {e}")
             traceback.print_exc()

    else:
        print(f"Unhandled event type {event.type}")

    # Acknowledge receipt to Stripe
    return HttpResponse(status=200)


@login_required
@require_POST # Expecting POST request with JSON data
def save_push_subscription_view(request):
    """
    Saves the PushSubscription object received from the browser
    to a WebPushDevice linked to the logged-in user.
    """
    try:
        # Load the JSON data sent from the frontend
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    # Basic validation of the received data structure
    if not data or 'endpoint' not in data or 'keys' not in data or \
       'p256dh' not in data['keys'] or 'auth' not in data['keys']:
        return JsonResponse({'status': 'error', 'message': 'Invalid subscription data format'}, status=400)

    # Extract subscription details
    endpoint = data['endpoint']
    p256dh = data['keys']['p256dh']
    auth = data['keys']['auth']

    try:
        # Use update_or_create to handle existing subscriptions for the same endpoint/user
        # or create a new one. We link it to the request.user.
        # 'registration_id' is the field WebPushDevice uses for the endpoint URL.
        # 'p256dh' and 'auth' are the fields for the keys.
        device, created = WebPushDevice.objects.update_or_create(
            user=request.user,
            registration_id=endpoint,
            defaults={
                'p256dh': p256dh,
                'auth': auth,
                'active': True, # Mark device as active
                # Optional: You might want to set the browser based on request headers
                # 'browser': request.headers.get('User-Agent', '')[:100] # Example
            }
        )

        if created:
            print(f"Saved new push device for user {request.user.username}")
        else:
            print(f"Updated existing push device for user {request.user.username}")

        return JsonResponse({'status': 'success', 'message': 'Subscription saved.'})

    except Exception as e:
        print(f"Error saving WebPushDevice: {e}")
        traceback.print_exc() # Print full traceback for debugging
        return JsonResponse({'status': 'error', 'message': 'Server error saving subscription.'}, status=500)
