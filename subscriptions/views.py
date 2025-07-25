# subscriptions/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.urls import reverse
from django.views.generic import TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseServerError, JsonResponse
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db import transaction

import stripe
import json
import traceback
from datetime import datetime, timezone

from .models import Plan, Subscription, NotifiedAlert # Your subscription models
from push_notifications.models import WebPushDevice # For saving push subscriptions
# from accounts.models import Profile, SavedLocation # Only if directly needed by these views

User = get_user_model()

# --- Subscription Lifecycle Views ---
class SubscriptionSuccessView(TemplateView):
    template_name = 'subscriptions/success.html'

class SubscriptionCancelView(TemplateView):
    template_name = 'subscriptions/cancel.html'



@login_required
def create_customer_portal_session_view(request):
    """
    Creates a Stripe Billing Portal session for the logged-in user
    and redirects them to the portal.
    """
    try:
        # Get the user's local subscription record
        # Assuming OneToOneField from User to Subscription is named 'subscription'
        # or ForeignKey from Subscription to User
        user_subscription = Subscription.objects.get(user=request.user)

        if not user_subscription.stripe_customer_id:
            messages.error(request, "Could not find your Stripe customer information.")
            return redirect('accounts:settings') # Or wherever appropriate

        if not user_subscription.is_active(): # Use your model's method
             messages.warning(request, "You do not have an active subscription to manage.")
             return redirect('subscriptions:plan_selection')


        stripe.api_key = settings.STRIPE_SECRET_KEY

        # URL to redirect back to after the portal session (e.g., user's settings page)
        return_url = request.build_absolute_uri(reverse('accounts:settings'))

        portal_session = stripe.billing_portal.Session.create(
            customer=user_subscription.stripe_customer_id,
            return_url=return_url,
        )
        # Redirect to the portal_session.url
        return redirect(portal_session.url, status=303)

    except Subscription.DoesNotExist:
        messages.warning(request, "You do not seem to have a subscription to manage.")
        return redirect('subscriptions:plan_selection') # Or 'accounts:settings'
    except stripe.error.StripeError as e:
        messages.error(request, f"Could not connect to subscription portal: {e}")
        print(f"Stripe Error creating portal session: {e}")
        return redirect('accounts:settings')
    except Exception as e:
        messages.error(request, f"An unexpected error occurred: {e}")
        print(f"Unexpected error creating portal session: {e}")
        traceback.print_exc() # Ensure traceback is imported
        return redirect('accounts:settings')




def subscription_plan_view(request):
#    print("--- DEBUG: Inside subscription_plan_view ---") # Check if view is hit

    all_plans_qs = Plan.objects.all() # Get the queryset
#    print(f"--- DEBUG: Plan.objects.all() found {all_plans_qs.count()} plans initially. ---")

    all_plans_qs = Plan.objects.filter(is_visible_on_page=True) # Only fetch visible plans

    # Your existing logic to order and process into plan_tiers/displayable_tiers
    # For example:
    all_plans_ordered = all_plans_qs.order_by('tier_name', 'billing_interval')

    plan_tiers = {}
    for plan in all_plans_ordered:
        if plan.tier_name not in plan_tiers:
            plan_tiers[plan.tier_name] = {
                'display_order': plan.display_order, 
                'features': plan.features.splitlines() if plan.features else []
            }
        if plan.billing_interval == 'month':
            plan_tiers[plan.tier_name]['month'] = plan
        elif plan.billing_interval == 'year':
            plan_tiers[plan.tier_name]['year'] = plan

    displayable_tiers = []
    for tier_name, data in plan_tiers.items():
        monthly_plan = data.get('month')
        yearly_plan = data.get('year')
        discount_percent = 0
        effective_monthly_price = None

        if yearly_plan and yearly_plan.price is not None:
            try:
                effective_monthly_price = yearly_plan.price / 12
            except TypeError:
                effective_monthly_price = None

        if monthly_plan and yearly_plan and monthly_plan.price > 0:
            twelve_month_price = monthly_plan.price * 12
            if twelve_month_price > yearly_plan.price:
                savings = twelve_month_price - yearly_plan.price
                discount_percent = round((savings / twelve_month_price) * 100)

        displayable_tiers.append({
            'tier_name': tier_name,
            'monthly_plan': monthly_plan,
            'yearly_plan': yearly_plan,
            'yearly_discount_percent': discount_percent,
            'features': data.get('features', []),
            'display_order': data.get('display_order', 0),
            'effective_monthly_price': effective_monthly_price,
            'is_monthly_purchasable': monthly_plan.is_purchasable if monthly_plan else False, # From Plan model
            'is_yearly_purchasable': yearly_plan.is_purchasable if yearly_plan else False,   # From Plan model
        })

    displayable_tiers.sort(key=lambda x: (x['display_order'], x['tier_name']))

    first_available_yearly_discount = 0
    for tier_data in displayable_tiers:
        if tier_data.get('yearly_plan') and tier_data.get('yearly_discount_percent', 0) > 0:
            first_available_yearly_discount = tier_data['yearly_discount_percent']
            break

    print(f"--- DEBUG: Number of displayable_tiers being sent to template: {len(displayable_tiers)} ---")

    context = {
        'plan_tiers': displayable_tiers,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
        'current_billing_preference': request.COOKIES.get('billingPreference', 'month'),
        'first_available_yearly_discount': first_available_yearly_discount,
    }
    return render(request, 'subscriptions/plan_selection.html', context)

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

    session_params = {
        'line_items': [{'price': price_id, 'quantity': 1}],
        'mode': 'subscription',
        'success_url': success_url,
        'cancel_url': cancel_url,
        'client_reference_id': str(request.user.id), # Ensure it's a string
        'payment_method_types': ['card'],
    }

    if request.user.email:
        session_params['customer_email'] = request.user.email

    try:
        checkout_session = stripe.checkout.Session.create(**session_params)
        return redirect(checkout_session.url, status=303)
    except stripe.error.StripeError as e:
        messages.error(request, f"Error communicating with Stripe: {e}")
        print(f"Stripe Error creating checkout session: {e}")
        return redirect('subscriptions:plan_selection')
    except Exception as e:
        messages.error(request, f"An unexpected error occurred: {e}")
        print(f"Checkout session creation Error: {e}")
        traceback.print_exc()
        return redirect('subscriptions:plan_selection')

# --- Stripe Webhook Handler ---
@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    payload = request.body
    sig_header = request.headers.get('stripe-signature')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    event = None

        # --- START: ADD THIS DEBUG PRINT AT THE VERY BEGINNING ---
    view_actual_webhook_secret = "STRIPE_WEBHOOK_SECRET_NOT_FOUND_IN_SETTINGS" # Default
    try:
        view_actual_webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        if view_actual_webhook_secret and isinstance(view_actual_webhook_secret, str) and len(view_actual_webhook_secret) > 20:
            print(f"DEBUG WEBHOOK VIEW: Function is using STRIPE_WEBHOOK_SECRET that starts with '{view_actual_webhook_secret[:15]}' and ends with '{view_actual_webhook_secret[-5:]}'.")
        else:
            print(f"DEBUG WEBHOOK VIEW: STRIPE_WEBHOOK_SECRET from settings appears short or invalid: '{str(view_actual_webhook_secret)[:100]}'")
    except AttributeError:
        print(f"DEBUG WEBHOOK VIEW: settings.STRIPE_WEBHOOK_SECRET is not defined at all!")
    except Exception as e_dbg_secret:
        print(f"DEBUG WEBHOOK VIEW: Error accessing settings.STRIPE_WEBHOOK_SECRET: {e_dbg_secret}")
    # --- END: ADD THIS DEBUG PRINT ---

    payload = request.body
    sig_header = request.headers.get('stripe-signature') # Standard casing used by Stripe
    
    # Use the secret that Django settings provides to this view
    endpoint_secret = view_actual_webhook_secret 
    event = None


    # Ensure API key is set for this view's Stripe calls
    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        print(f"\nWebhook received: Event ID: {event.id}, Type: {event.type}")
    except ValueError as e:
        print(f"!!! Webhook error parsing payload: {e}")
        return HttpResponseBadRequest("Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        print(f"!!! Webhook signature verification failed: {e}")
        return HttpResponseBadRequest("Invalid signature")
    except Exception as e:
        print(f"!!! Webhook construction error: {e}")
        traceback.print_exc()
        return HttpResponseBadRequest(f"Webhook construction error: {e}")

    # --- Handle checkout.session.completed event ---
    if event.type == 'checkout.session.completed':
        session = event.data.object
        print(f"--- Processing checkout.session.completed ---")
        print(f"  Stripe Session ID: {session.id}")
        print(f"  Stripe Customer ID from session: {session.get('customer')}")
        print(f"  Stripe Subscription ID from session: {session.get('subscription')}")
        print(f"  Client Reference ID (Django User ID) from session: {session.get('client_reference_id')}")

        client_reference_id = session.get('client_reference_id')
        stripe_customer_id_from_session = session.get('customer')
        stripe_subscription_id_from_session = session.get('subscription')

        if not all([client_reference_id, stripe_customer_id_from_session, stripe_subscription_id_from_session]):
            error_msg = "Webhook error: Missing critical IDs in checkout.session.completed!"
            print(f"  !!! {error_msg} - ClientRef: {client_reference_id}, CustID: {stripe_customer_id_from_session}, SubID: {stripe_subscription_id_from_session}")
            return HttpResponseBadRequest("Missing critical IDs in session.")

        User = get_user_model()
        try:
            user = User.objects.get(id=client_reference_id)
            print(f"  Found Django User: {user.username} (ID: {user.id})")

            try:
                print(f"  Attempting to retrieve Stripe Subscription object with ID: {stripe_subscription_id_from_session}")
                stripe_sub_object = stripe.Subscription.retrieve(stripe_subscription_id_from_session)
                print(f"  Successfully retrieved Stripe Subscription object. Status: {stripe_sub_object.status}")
                print(f"    Stripe Sub Plan ID (Price ID): {stripe_sub_object.plan.id if stripe_sub_object.plan else 'None'}")
                print(f"    Stripe Sub Current Period End Timestamp: {stripe_sub_object.get('current_period_end')}")
                print(f"    Stripe Sub Trial End Timestamp: {stripe_sub_object.get('trial_end')}")


                stripe_price_id = stripe_sub_object.plan.id if stripe_sub_object.plan else None
                period_end_timestamp = stripe_sub_object.get('current_period_end') or stripe_sub_object.get('trial_end')
                
                current_period_end_dt = None
                if period_end_timestamp is not None:
                    try:
                        current_period_end_dt = datetime.fromtimestamp(period_end_timestamp, tz=timezone.utc)
                        print(f"      Converted Period End Datetime: {current_period_end_dt}")
                    except Exception as e_conv:
                        print(f"      !!! ERROR converting timestamp {period_end_timestamp}: {e_conv}")
                
                if not stripe_price_id:
                    print(f"  !!! Webhook Error: Retrieved Stripe Subscription (ID: {stripe_subscription_id_from_session}) is missing a plan ID.")
                    return HttpResponseServerError("Stripe Subscription missing plan ID.")

                try:
                    local_plan_obj = Plan.objects.get(stripe_price_id=stripe_price_id)
                    print(f"  Found local Plan in DB: {local_plan_obj.name}")

                    subscription_defaults = {
                        'plan': local_plan_obj,
                        'stripe_subscription_id': stripe_subscription_id_from_session,
                        'stripe_customer_id': stripe_customer_id_from_session,
                        'status': stripe_sub_object.status,
                        'current_period_end': current_period_end_dt,
                    }
                    print(f"  Attempting update_or_create Subscription with defaults: {subscription_defaults}")

                    with transaction.atomic():
                        local_subscription, created = Subscription.objects.update_or_create(
                            user=user,
                            defaults=subscription_defaults
                        )
                    
                    if created:
                        print(f"  CREATED local Subscription DB record for user {user.username}. ID: {local_subscription.pk}")
                    else:
                        print(f"  UPDATED local Subscription DB record for user {user.username}. ID: {local_subscription.pk}")
                    print(f"    Local sub final status: {local_subscription.status}, period_end: {local_subscription.current_period_end}")

                except Plan.DoesNotExist:
                    print(f"  !!! Webhook error: Local Plan with Stripe Price ID {stripe_price_id} not found.")
                    return HttpResponseServerError("Local Plan not found.")
                except Exception as e_db:
                    print(f"  !!! Webhook error saving local Subscription to DB: {e_db}")
                    traceback.print_exc()
                    return HttpResponseServerError("DB error saving local subscription.")

            except stripe.error.StripeError as e_sub_retrieve:
                print(f"  !!! Webhook error retrieving Stripe Subscription {stripe_subscription_id_from_session}: {e_sub_retrieve}")
                traceback.print_exc()
                return HttpResponseServerError("Stripe API error retrieving subscription.")
            except Exception as e_inner_processing:
                print(f"  !!! Webhook error during inner processing for user {user.username}: {e_inner_processing}")
                traceback.print_exc()
                return HttpResponseServerError("Inner processing error during subscription update.")

        except User.DoesNotExist:
            print(f"  Webhook error: User with client_reference_id {client_reference_id} not found.")
            return HttpResponseBadRequest("User not found from client_reference_id.")
        
        print(f"--- Finished processing checkout.session.completed successfully ---")
        return HttpResponse(status=200)

    # --- Handle successful payment (renewal) ---
    elif event.type == 'invoice.paid':
        invoice = event.data.object
        stripe_subscription_id = invoice.get('subscription')
        stripe_customer_id = invoice.get('customer')
        print(f"Processing 'invoice.paid' for subscription_id: {stripe_subscription_id}, customer_id: {stripe_customer_id}")

        if invoice.get('billing_reason') == 'subscription_cycle' and invoice.get('paid') and stripe_subscription_id:
            try:
                stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
                local_subscription = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)

                local_subscription.status = stripe_sub.status
                new_period_end_dt = None
                if stripe_sub.current_period_end:
                    try:
                        new_period_end_dt = datetime.fromtimestamp(stripe_sub.current_period_end, tz=timezone.utc)
                    except Exception as e_conv:
                        print(f"  !!! ERROR converting current_period_end timestamp {stripe_sub.current_period_end} for invoice.paid: {e_conv}")
                local_subscription.current_period_end = new_period_end_dt
                
                if not local_subscription.stripe_customer_id and stripe_customer_id: # Should already be set
                    local_subscription.stripe_customer_id = stripe_customer_id
                
                local_subscription.save()
                print(f"  Updated subscription {stripe_subscription_id} on {event.type}. Status: {local_subscription.status}, New Period End: {local_subscription.current_period_end}")
            except Subscription.DoesNotExist:
                print(f"  !!! Webhook Error (invoice.paid): Subscription {stripe_subscription_id} not found in local DB.")
            except stripe.error.StripeError as e_stripe:
                print(f"  !!! Stripe API Error (invoice.paid) for {stripe_subscription_id}: {e_stripe}")
            except Exception as e_general:
                print(f"  !!! General Error (invoice.paid) for {stripe_subscription_id}: {e_general}")
                traceback.print_exc()
        else:
            print(f"  Ignoring '{event.type}' (Reason: {invoice.get('billing_reason')}, Paid: {invoice.get('paid')}, SubID: {stripe_subscription_id})")
        return HttpResponse(status=200)

    elif event.type == 'customer.subscription.created' or event.type == 'customer.subscription.updated':
            stripe_sub_object = event.data.object  # The event data IS the subscription object
            stripe_subscription_id = stripe_sub_object.id
            stripe_customer_id = stripe_sub_object.customer 
            
            print(f"--- Processing '{event.type}' for subscription {stripe_subscription_id} ---")
            print(f"  Stripe Sub Status: {stripe_sub_object.status}")
            print(f"  Stripe Sub Plan ID (Price ID): {stripe_sub_object.plan.id if stripe_sub_object.plan else 'None'}")
            print(f"  Stripe Sub Current Period End Timestamp: {stripe_sub_object.get('current_period_end')}") # <<< Key log
            print(f"  Stripe Sub Trial End Timestamp: {stripe_sub_object.get('trial_end')}")
            print(f"  Stripe Sub Canceled At Timestamp: {stripe_sub_object.get('canceled_at')}")
            print(f"  Stripe Sub Ended At Timestamp: {stripe_sub_object.get('ended_at')}")

            try:
                # User should already exist if checkout.session.completed was processed
                # Find the local subscription record by Stripe Subscription ID
                # It should have been created by checkout.session.completed handler
                local_subscription = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)
                print(f"  Found local subscription for user: {local_subscription.user.username}")

                # Update status
                local_subscription.status = stripe_sub_object.status
                
                # Update current_period_end (prioritize current_period_end, then trial_end)
                new_period_end_dt = None
                timestamp_to_use = stripe_sub_object.get('current_period_end') or stripe_sub_object.get('trial_end')
                
                if stripe_sub_object.status == 'canceled' and stripe_sub_object.get('canceled_at'):
                    timestamp_to_use = stripe_sub_object.get('canceled_at')
                elif stripe_sub_object.get('ended_at'): # If it's definitively ended
                     timestamp_to_use = stripe_sub_object.get('ended_at')

                if timestamp_to_use is not None:
                    try:
                        new_period_end_dt = datetime.fromtimestamp(timestamp_to_use, tz=timezone.utc)
                        print(f"    Converted timestamp ({timestamp_to_use}) for period_end: {new_period_end_dt}")
                    except Exception as e_conv:
                        print(f"  !!! ERROR converting timestamp {timestamp_to_use} for {event.type}: {e_conv}")
                local_subscription.current_period_end = new_period_end_dt

                # Update plan if it changed
                if stripe_sub_object.plan and \
                   (local_subscription.plan is None or local_subscription.plan.stripe_price_id != stripe_sub_object.plan.id):
                    try:
                        new_plan_from_stripe = Plan.objects.get(stripe_price_id=stripe_sub_object.plan.id)
                        local_subscription.plan = new_plan_from_stripe
                        print(f"  Updated local plan to: {new_plan_from_stripe.name}")
                    except Plan.DoesNotExist:
                        print(f"  !!! Error: New plan {stripe_sub_object.plan.id} not found in local DB during {event.type}.")
                        # Potentially log this as an error and don't change plan, or set plan to None
                        # local_subscription.plan = None 
                
                # Ensure customer_id is up-to-date
                if not local_subscription.stripe_customer_id and stripe_customer_id:
                    local_subscription.stripe_customer_id = stripe_customer_id
                elif local_subscription.stripe_customer_id != stripe_customer_id: # Should not happen for same sub
                     local_subscription.stripe_customer_id = stripe_customer_id # Update if different


                local_subscription.save()
                print(f"  Updated local subscription {stripe_subscription_id} on '{event.type}'. New status: {local_subscription.status}, Period End: {local_subscription.current_period_end}")

            except Subscription.DoesNotExist:
                print(f"  !!! Webhook Error ({event.type}): Subscription {stripe_subscription_id} not found in local DB. This might be an issue if checkout.session.completed was missed or failed.")
                # If it doesn't exist, we might want to create it here if we can reliably find the user.
                # This requires client_reference_id from the session, which isn't directly on the subscription event.
                # For now, we primarily rely on checkout.session.completed to create it.
            except Exception as e_general:
                print(f"  !!! General Error handling '{event.type}' for subscription {stripe_subscription_id}: {e_general}")
                traceback.print_exc()
                return HttpResponseServerError(f"Server error processing {event.type}")
            
            print(f"--- Finished processing {event.type} ---")
            return HttpResponse(status=200)




    # --- Handle subscription updates & deletions ---
    elif event.type == 'customer.subscription.updated' or event.type == 'customer.subscription.deleted':
        stripe_sub = event.data.object
        stripe_subscription_id = stripe_sub.id
        print(f"Processing '{event.type}' for subscription {stripe_subscription_id}")
        try:
            local_subscription = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)
            local_subscription.status = stripe_sub.status
            
            new_period_end_dt = None
            timestamp_to_use_for_period_end = stripe_sub.get('current_period_end')
            if stripe_sub.status == 'canceled' and stripe_sub.get('canceled_at'):
                timestamp_to_use_for_period_end = stripe_sub.get('canceled_at')
            elif stripe_sub.get('ended_at'):
                 timestamp_to_use_for_period_end = stripe_sub.get('ended_at')

            if timestamp_to_use_for_period_end is not None:
                try: new_period_end_dt = datetime.fromtimestamp(timestamp_to_use_for_period_end, tz=timezone.utc)
                except Exception as e: print(f"  !!! Error converting final timestamp: {e}")
            local_subscription.current_period_end = new_period_end_dt

            if stripe_sub.plan and (not local_subscription.plan or local_subscription.plan.stripe_price_id != stripe_sub.plan.id):
                try:
                    new_plan_from_stripe = Plan.objects.get(stripe_price_id=stripe_sub.plan.id)
                    local_subscription.plan = new_plan_from_stripe
                    print(f"  Updated plan for subscription {stripe_subscription_id} to {new_plan_from_stripe.name}")
                except Plan.DoesNotExist:
                    print(f"  !!! Error: New plan {stripe_sub.plan.id} not found in DB during {event.type}.")
            
            local_subscription.save()
            print(f"  Updated local subscription {stripe_subscription_id} on '{event.type}'. New status: {local_subscription.status}, Period End: {local_subscription.current_period_end}")
        except Subscription.DoesNotExist:
            print(f"  !!! Webhook Error ({event.type}): Subscription {stripe_subscription_id} not found.")
        except Exception as e_general:
            print(f"  !!! General Error ({event.type}) for {stripe_subscription_id}: {e_general}")
            traceback.print_exc()
        return HttpResponse(status=200)

    # --- Handle failed payments ---
    elif event.type == 'invoice.payment_failed':
        invoice = event.data.object
        stripe_subscription_id = invoice.get('subscription')
        print(f"Processing '{event.type}' for subscription {stripe_subscription_id}")
        if stripe_subscription_id:
            try:
                stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
                local_subscription = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)
                local_subscription.status = stripe_sub.status 
                local_subscription.save(update_fields=['status'])
                print(f"  Updated subscription {stripe_subscription_id} status to '{local_subscription.status}' on '{event.type}'.")
            except Subscription.DoesNotExist:
                print(f"  !!! Webhook Error ({event.type}): Subscription {stripe_subscription_id} not found.")
            except stripe.error.StripeError as e:
                print(f"  !!! Stripe Error handling {event.type} for {stripe_subscription_id}: {e}")
            except Exception as e:
                print(f"  !!! Error handling {event.type} for {stripe_subscription_id}: {e}")
                traceback.print_exc()
        else:
            print(f"  Ignoring {event.type} as no subscription ID was found on the invoice.")
        return HttpResponse(status=200)

    else:
        print(f"Unhandled event type {event.type}")
        return HttpResponse(status=200)


# --- Save Push Subscription View (Keep this as it was) ---
@login_required
@require_POST
def save_push_subscription_view(request):
    # ... your existing save_push_subscription_view code ...
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    if not data or 'endpoint' not in data or 'keys' not in data or \
       'p256dh' not in data['keys'] or 'auth' not in data['keys']:
        return JsonResponse({'status': 'error', 'message': 'Invalid subscription data format'}, status=400)
    endpoint = data['endpoint']
    p256dh = data['keys']['p256dh']
    auth = data['keys']['auth']
    try:
        device, created = WebPushDevice.objects.update_or_create(
            user=request.user, registration_id=endpoint,
            defaults={'p256dh': p256dh, 'auth': auth, 'active': True}
        )
        if created: print(f"Saved new push device for user {request.user.username}")
        else: print(f"Updated existing push device for user {request.user.username}")
        return JsonResponse({'status': 'success', 'message': 'Subscription saved.'})
    except Exception as e:
        print(f"Error saving WebPushDevice: {e}")
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': 'Server error saving subscription.'}, status=500)


@login_required
@require_POST # Or allow DELETE method if your JS sends DELETE
@csrf_exempt # If using POST and CSRF token is sent in headers, might not need this, 
             # but service worker / JS fetch requests can be tricky with CSRF if not SPA.
             # For API-like endpoints, session auth + CSRF header is good.
             # If you keep @csrf_exempt, ensure your endpoint is not vulnerable.
             # A better way is to ensure JS sends X-CSRFToken header. My JS example does.
def delete_push_subscription_view(request):
    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint')

        if not endpoint:
            return JsonResponse({'status': 'error', 'message': 'Missing endpoint.'}, status=400)

        # Find and delete/deactivate the device for the current user
        devices_deleted, _ = WebPushDevice.objects.filter(user=request.user, registration_id=endpoint).delete()
        # Or, to deactivate:
        # devices_updated = WebPushDevice.objects.filter(user=request.user, registration_id=endpoint).update(active=False)


        if devices_deleted > 0: # Or devices_updated > 0 if deactivating
            print(f"Deactivated/Deleted push device with endpoint {endpoint} for user {request.user.username}")
            return JsonResponse({'status': 'success', 'message': 'Unsubscribed successfully.'})
        else:
            print(f"No active push device found with endpoint {endpoint} for user {request.user.username} to delete/deactivate.")
            return JsonResponse({'status': 'error', 'message': 'Subscription not found or already inactive.'}, status=404)

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)
    except Exception as e:
        print(f"Error deleting push subscription: {e}")
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': 'Server error during unsubscription.'}, status=500)
