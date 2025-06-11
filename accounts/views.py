# /srv/radar_site_prod/accounts/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.db import transaction
from django.views.generic import TemplateView
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.html import strip_tags
from django.http import JsonResponse
import json


from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from decimal import Decimal, InvalidOperation
import traceback
from django.contrib.auth import login, logout, get_user_model

# App-specific imports
from .forms import UserSignUpForm, FamilyInvitationForm
from .models import Profile, SavedLocation, Family, FamilyInvitation
from subscriptions.models import Subscription
from .models import UserLocationHistory


User = get_user_model()

# --- Service Worker View ---
class ServiceWorkerView(TemplateView):
    template_name = 'sw.js'
    content_type = 'application/javascript'

# --- Signup View ---
@transaction.atomic
def sign_up(request):
    initial_data = {'email': request.GET.get('email', '')}
    
    if request.method == 'POST':
        form = UserSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            town = form.cleaned_data.get('town')
            state = form.cleaned_data.get('state')
            
            profile, created = Profile.objects.get_or_create(user=user)
            profile.town = town
            profile.state = state
            profile.save()
            
            # Check for and process family invitation token from session
            invitation_token = request.session.get('family_invitation_token')
            if invitation_token:
                try:
                    invitation = FamilyInvitation.objects.get(token=invitation_token, is_accepted=False)
                    family = invitation.family
                    
                    if family.members.count() < 3: # Family plan limit check
                        family.members.add(user)
                        invitation.is_accepted = True
                        invitation.accepted_at = timezone.now()
                        invitation.save()
                        messages.success(request, f"Welcome! You have successfully joined the '{family.name}' family plan.")
                    else:
                        messages.warning(request, "Your account was created, but the family you were invited to is already full.")

                    del request.session['family_invitation_token']
                except FamilyInvitation.DoesNotExist:
                    messages.warning(request, "Your account was created, but the family invitation link was invalid or has already been used.")
            else:
                messages.success(request, f"Welcome, {user.username}! Your account has been created successfully.")
            
            # Send Welcome Email (if configured to do so via signals)
            # The signal handler in accounts/signals.py will take care of this automatically

            login(request, user)  
            return redirect('pages:home') # Redirect to homepage
    else:
        form = UserSignUpForm(initial=initial_data)
    
    return render(request, 'registration/signup.html', {'form': form})


# --- Consolidated Account Settings View ---
@login_required
def user_settings_view(request):
    """
    A single, unified view to manage all aspects of the user settings page,
    including location management and family plan features for all premium users.
    """
    profile = request.user.profile
    # It's good practice to provide a contact email in your User-Agent string for Nominatim
    geolocator = Nominatim(user_agent=f"unfortunateneighbor_weather_app/{settings.DEFAULT_FROM_EMAIL}")
    
    # 1. Centralized premium access check using the property from your Profile model.
    # This fixes the "beta tester not getting access" issue.
    has_premium_access = profile.has_premium_access 
    max_locations = 3 if has_premium_access else 1

    # 2. Family Plan Initialization Logic.
    # For this app, any user with premium access (including beta testers) can manage a family.
    is_family_owner = False
    can_invite_more = False
    user_family = None
    family_plan_limit = 3
    
    if has_premium_access:
        is_family_owner = True
        # Get or create the Family object for this user
        user_family, created = Family.objects.get_or_create(
            owner=request.user, 
            defaults={'name': f"{request.user.username}'s Family"}
        )
        
        # Correctly calculate available invitation slots
        accepted_member_count = user_family.members.count()
        pending_invitation_count = user_family.invitations.filter(is_accepted=False).count()
        total_slots_used = accepted_member_count + pending_invitation_count
        
        if total_slots_used < family_plan_limit:
            can_invite_more = True
    
    
    is_family_member = request.user.families.exists()
     
    # 3. Handle ALL POST Requests from the Settings Page
    if request.method == 'POST':
        # --- Handle Family Plan Invitation ---
        if 'send_invitation' in request.POST:
            if is_family_owner and can_invite_more and user_family:
                invitation_form = FamilyInvitationForm(request.POST)
                if invitation_form.is_valid():
                    email_to_invite = invitation_form.cleaned_data['email']
                    # Check if user is already a member or already invited
                    if User.objects.filter(email=email_to_invite).filter(families=user_family).exists():
                         messages.warning(request, f"The user with email {email_to_invite} is already a member of your family.")
                    elif FamilyInvitation.objects.filter(family=user_family, email_to_invite=email_to_invite, is_accepted=False).exists():
                         messages.warning(request, f"An invitation has already been sent to {email_to_invite} and is pending.")
                    else:
                        invitation = FamilyInvitation.objects.create(family=user_family, sent_by=request.user, email_to_invite=email_to_invite)
                        # Send invitation email
                        try:
                            site_name = getattr(settings, 'SITE_NAME_DISPLAY', 'Unfortunate Neighbor Weather')
                            invitation_link = request.build_absolute_uri(reverse('accounts:accept_invitation', kwargs={'token': invitation.token}))
                            email_context = {
                                'inviter_name': request.user.username, 'family_name': user_family.name,
                                'invitation_link': invitation_link, 'site_name': site_name,
                            }
                            subject = render_to_string('accounts/email/family_invitation_subject.txt', email_context).strip()
                            html_message = render_to_string('accounts/email/family_invitation_body.html', email_context)
                            send_mail(
                                subject=subject, message=strip_tags(html_message),
                                from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[email_to_invite],
                                html_message=html_message, fail_silently=False
                            )
                            messages.success(request, f"Invitation sent to {email_to_invite}.")
                        except Exception as e:
                            messages.error(request, f"There was an error sending the invitation email: {e}")
                            print(f"ERROR sending family invitation email: {e}")
                            traceback.print_exc()
                else: 
                    messages.error(request, "Please enter a valid email address.")
            else:
                messages.error(request, "You are not eligible to send invitations at this time.")

        # --- Handle Setting Default Location ---
        elif 'set_as_default_action' in request.POST:
            location_id_to_make_default = request.POST.get('make_default_location_id')
            try:
                with transaction.atomic():
                    profile.saved_locations.update(is_default=False)
                    new_default_location = SavedLocation.objects.get(pk=location_id_to_make_default, profile=profile)
                    new_default_location.is_default = True
                    new_default_location.save()
                    messages.success(request, f"'{new_default_location.location_name}' is now your default location.")
            except SavedLocation.DoesNotExist:
                messages.error(request, "Selected location not found or permission denied.")
            except Exception as e:
                messages.error(request, f"An error occurred: {e}")

        # --- Handle Deleting a Location ---
        elif 'delete_location' in request.POST:
            location_id_to_delete = request.POST.get('delete_location')
            try:
                loc_to_delete = SavedLocation.objects.get(pk=location_id_to_delete, profile=profile)
                loc_name = loc_to_delete.location_name
                was_default = loc_to_delete.is_default
                loc_to_delete.delete()
                messages.success(request, f"Location '{loc_name}' was deleted.")
                if was_default and profile.saved_locations.exists():
                    new_default = profile.saved_locations.all().order_by('pk').first()
                    if new_default:
                        new_default.is_default = True
                        new_default.save()
                        messages.info(request, f"'{new_default.location_name}' was automatically set as your new default.")
            except SavedLocation.DoesNotExist:
                messages.error(request, "Location not found or permission denied.")

        # --- Handle Toggling Notifications for a Location ---
        elif 'toggle_notification_action' in request.POST:
            location_id_to_toggle = request.POST.get('toggle_notification_loc_id')
            if location_id_to_toggle:
                try:
                    loc_to_toggle = SavedLocation.objects.get(pk=location_id_to_toggle, profile=profile)
                    loc_to_toggle.receive_notifications = not loc_to_toggle.receive_notifications
                    loc_to_toggle.save()
                    status_text = "enabled" if loc_to_toggle.receive_notifications else "disabled"
                    messages.success(request, f"Alert notifications {status_text} for '{loc_to_toggle.location_name}'.")
                except SavedLocation.DoesNotExist:
                    messages.error(request, "Location not found or permission denied.")
            else:
                messages.error(request, "Invalid request to toggle notifications.")

        # --- Handle Manual Location Add ---
        elif 'add_manual_location' in request.POST:
            current_location_count = profile.saved_locations.count()
            if current_location_count < max_locations:
                manual_query = request.POST.get('manual_location', '').strip()
                location_type = request.POST.get('location_type_manual', 'other')
                if manual_query:
                    try:
                        location = geolocator.geocode(manual_query, timeout=10)
                        if location:
                            has_default = profile.saved_locations.filter(is_default=True).exists()
                            SavedLocation.objects.create(
                                profile=profile, location_name=location.address,
                                latitude=Decimal(location.latitude), longitude=Decimal(location.longitude),
                                is_default=(not has_default), location_type_label=location_type
                            )
                            messages.success(request, f"Location '{location.address}' added.")
                        else:
                            messages.error(request, f"Could not find coordinates for '{manual_query}'.")
                    except Exception as e:
                        messages.error(request, f"An error occurred while adding location: {e}")
                else:
                    messages.warning(request, "Please enter a location to add.")
            else:
                messages.error(request, f"You have reached your limit of {max_locations} saved location(s).")
        
        # After any POST action, redirect back to the same page to prevent re-submission
        return redirect('accounts:settings')

    # --- For a GET Request ---
    else:
        invitation_form = FamilyInvitationForm()

    # Prepare context for the template
    saved_locations = profile.saved_locations.all().order_by('-is_default', 'pk')
    can_add_location = saved_locations.count() < max_locations
    
    family_members = user_family.members.all() if user_family else []
    pending_invitations = user_family.invitations.filter(is_accepted=False) if user_family else []

        
    context = {
        'saved_locations': saved_locations,
        'has_premium_access': has_premium_access,
        'can_add_location': can_add_location,
        'max_locations': max_locations,
        'location_type_choices': SavedLocation.LOCATION_TYPE_CHOICES,
        'vapid_public_key': getattr(settings, 'VAPID_PUBLIC_KEY_FOR_TEMPLATE', None),
        'is_family_member': is_family_member,
        
        # Family plan context
        'invitation_form': invitation_form,
        'is_family_owner': is_family_owner,
        'can_invite_more': can_invite_more,
        'family_members': family_members,
        'pending_invitations': pending_invitations,
        'family_plan_limit': family_plan_limit,
    }
    return render(request, 'accounts/settings.html', context)



# --- Invitation Acceptance View ---
def accept_invitation_view(request, token):
    # ... (code from message #218) ...
    try:
        invitation = FamilyInvitation.objects.get(token=token, is_accepted=False)
    except FamilyInvitation.DoesNotExist:
        messages.error(request, "This invitation link is invalid or has already been used.")
        return redirect('pages:home')

    if request.user.is_authenticated:
        # Check if the logged-in user's email matches the invitation
        if request.user.email != invitation.email_to_invite:
            messages.error(request, "This invitation is for a different email address. Please log out and sign up with the correct email, or log in to the correct account.")
            return redirect('accounts:settings')
        
        family = invitation.family
        if family.members.count() >= 3:
            messages.warning(request, "The family you were invited to is currently full.")
            return redirect('accounts:settings')

        family.members.add(request.user)
        invitation.is_accepted = True
        invitation.accepted_at = timezone.now()
        invitation.save()
        messages.success(request, f"You have successfully joined the '{family.name}' family plan!")
        return redirect('accounts:settings') 
    else:
        # User is not logged in, redirect them to sign up
        request.session['family_invitation_token'] = str(token)
        messages.info(request, "Please sign up or log in to accept your family plan invitation.")
        signup_url = reverse('accounts:signup')
        return redirect(f'{signup_url}?email={invitation.email_to_invite}')


# --- Account Deletion Views ---
@login_required
def delete_account_confirm_view(request):
    # ... (code from message #186) ...
    has_active_stripe_subscription = False
    stripe_portal_url = None
    try:
        if request.user.profile.has_premium_access and hasattr(request.user, 'subscription') and request.user.subscription and request.user.subscription.stripe_customer_id:
             has_active_stripe_subscription = True
             stripe_portal_url = reverse('subscriptions:create_customer_portal_session')
    except Exception as e:
        print(f"Error checking for active subscription in delete_account_confirm_view: {e}")

    context = {
        'has_active_stripe_subscription': has_active_stripe_subscription,
        'stripe_portal_url': stripe_portal_url
    }
    return render(request, 'registration/delete_account_confirm.html', context)


@login_required
@require_POST 
@transaction.atomic 
def delete_account_perform_view(request):
    # ... (code from message #192, now with correct imports at top of file) ...
    user_to_delete_instance = request.user
    user_id_to_delete = user_to_delete_instance.pk
    user_email_for_farewell = user_to_delete_instance.email
    user_username_for_farewell = user_to_delete_instance.username

    # Final check for active subscription before deleting
    if hasattr(user_to_delete_instance, 'subscription') and user_to_delete_instance.subscription and user_to_delete_instance.subscription.is_active():
        messages.error(request, "Deletion failed: You still have an active subscription.")
        return redirect('accounts:delete_account_confirm') 

    logout(request) 
    
    try:
        actual_user_to_delete = User.objects.get(pk=user_id_to_delete)
        actual_user_to_delete.delete() 
        messages.success(request, f"Account '{user_username_for_farewell}' has been permanently deleted.")
    except User.DoesNotExist:
        messages.error(request, "Could not find user account to delete.")
        return redirect('pages:home') 
    except Exception as e_del:
        messages.error(request, "An error occurred while deleting your account.")
        traceback.print_exc()
        return redirect('pages:home')

    # Send Farewell Email
    if user_email_for_farewell:
        try:
            site_name = getattr(settings, 'SITE_NAME_DISPLAY', 'Unfortunate Neighbor Weather')
            email_context = {'user_username': user_username_for_farewell, 'site_name': site_name}
            subject = render_to_string('accounts/email/farewell_email_subject.txt', email_context).strip()
            html_message = render_to_string('accounts/email/farewell_email_body.html', email_context)
            plain_message = strip_tags(html_message) # Using strip_tags
            send_mail(
                subject, plain_message, settings.DEFAULT_FROM_EMAIL, [user_email_for_farewell], 
                html_message=html_message, fail_silently=False
            )
            print(f"Farewell email sent to former user: {user_email_for_farewell}")
        except Exception as e_email:
            print(f"ERROR sending farewell email to {user_email_for_farewell}: {e_email}")
            traceback.print_exc()
    
    return redirect('pages:home')


@login_required
@require_POST # This view should only accept POST requests
def update_location_view(request):
    """
    Receives location updates from a user's browser via JavaScript
    and saves it to their location history.
    """
    try:
        data = json.loads(request.body)
        lat = data.get('lat')
        lon = data.get('lon')

        if lat is None or lon is None:
            return JsonResponse({'status': 'error', 'message': 'Missing latitude or longitude.'}, status=400)

        # Create a new location history record for the logged-in user
        UserLocationHistory.objects.create(
            user=request.user,
            latitude=Decimal(lat),
            longitude=Decimal(lon)
        )

        return JsonResponse({'status': 'success', 'message': 'Location updated.'})

    except (json.JSONDecodeError, InvalidOperation, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid location data format.'}, status=400)
    except Exception as e:
        print(f"ERROR in update_location_view for user {request.user.username}: {e}")
        traceback.print_exc() # This will log the full error to your Gunicorn logs
        return JsonResponse({'status': 'error', 'message': 'An unexpected server error occurred.'}, status=500)


@login_required
def family_map_view(request):
    # A user can view the map if they are an owner of a family OR a member of one.
    # Your profile.has_premium_access property already covers owners (as beta testers or subscribers).
    # We can add a check for simple members too.
    is_in_family = request.user.profile.has_premium_access or request.user.families.exists()

    if not is_in_family:
        messages.warning(request, "You must be part of a family plan to view the Family Map.")
        return redirect('accounts:settings') # Redirect them to settings if not in a family

    context = {
        'mapbox_access_token': settings.MAPBOX_ACCESS_TOKEN,
    }
    return render(request, 'accounts/family_map.html', context)



@login_required
def family_locations_api_view(request):
    """
    API endpoint that returns the latest location data for a user's family members.
    """
    user = request.user
    family = None

    if hasattr(user, 'owned_family'):
        family = user.owned_family
    elif user.families.exists():
        family = user.families.first()

    if not family:
        return JsonResponse({'status': 'error', 'message': 'User is not part of a family.'}, status=403)

    owner = family.owner
    members = list(family.members.all())
    all_family_members = list(set([owner] + members)) # Use set to handle owner being a member

    locations_data = []
    for member in all_family_members:
        latest_location = member.location_history.order_by('-timestamp').first()
        if latest_location:
            locations_data.append({
                'username': member.username,
                'latitude': latest_location.latitude,
                'longitude': latest_location.longitude,
                'timestamp_iso': latest_location.timestamp.isoformat(),
                'is_in_warned_area': latest_location.is_in_warned_area,
            })

    # --- THIS IS THE KEY CHANGE ---
    # Wrap the list in a dictionary. This is a more standard API response format.
    response_data = {
        'status': 'success',
        'family_members': locations_data
    }
    return JsonResponse(response_data)


@login_required
@require_POST # This view should only be accessed via a POST request (from a form)
def remove_family_member_view(request, member_id):
    """
    Allows a family owner to remove a member from their family.
    """
    # Ensure the logged-in user is actually a family owner
    if not hasattr(request.user, 'owned_family'):
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('accounts:settings')

    family = request.user.owned_family
    
    # Get the member to be removed, ensuring they are actually a member of this family
    member_to_remove = get_object_or_404(User, pk=member_id, families=family)

    if member_to_remove:
        family.members.remove(member_to_remove)
        messages.success(request, f"Successfully removed {member_to_remove.username} from your family plan.")
    else:
        messages.error(request, "Could not find the specified member in your family.")

    return redirect('accounts:settings')


@login_required
@require_POST
def leave_family_view(request):
    """
    Allows a member to remove themselves from a family they have joined.
    """
    # Find the family the user is a member of
    # .first() is used assuming a user can only be a member of one family.
    # If they can be in multiple, this logic would need to be adjusted.
    family_membership = request.user.families.first() 
    
    if family_membership:
        family_membership.members.remove(request.user)
        messages.success(request, f"You have successfully left the '{family_membership.name}' family plan.")
    else:
        messages.error(request, "You are not currently a member of a family plan.")

    return redirect('accounts:settings')


@login_required
def should_track_location_view(request):
    """
    An API endpoint for the client to ask if it should enable location tracking.
    Returns {'should_track': True} if there are active warnings near the user's
    last known location, otherwise returns {'should_track': False}.
    """
    user = request.user

    # We only need to check for family members
    is_in_family = hasattr(user, 'owned_family') or user.families.exists()
    if not is_in_family:
        return JsonResponse({'should_track': False})

    # Find the user's last known location from the database
    last_location = UserLocationHistory.objects.filter(user=user).order_by('-timestamp').first()

    if not last_location:
        # If we have no location history, we can't check for nearby alerts.
        # We could default to 'False', or maybe 'True' to get an initial position.
        # Let's default to False to be privacy-conscious.
        return JsonResponse({'should_track': False})

    try:
        # Use the same logic as your background task to check for alerts near this point
        user_agent = getattr(settings, 'ADMIN_EMAIL_FOR_NWS_USER_AGENT', 'DjangoWeatherApp/1.0')
        # You would need to import your helper functions for this to work
        from subscriptions.tasks import fetch_alerts_by_zone_or_point 

        # We check for any high-priority warnings (e.g., Tornado, Severe Thunderstorm)
        # You can customize this list
        warning_events = [
            "Tornado Warning", "Severe Thunderstorm Warning", "Flash Flood Warning",
            "Extreme Wind Warning", "Tornado Watch", "Severe Thunderstorm Watch"
        ]

        # Fetch alerts by point using the last known coordinates
        active_alerts = fetch_alerts_by_zone_or_point(None, last_location.latitude, last_location.longitude, user_agent)

        should_track = False
        for alert in active_alerts:
            if alert.get('event') in warning_events:
                should_track = True
                break # Found a relevant warning, no need to check further

        print(f"SHOULD_TRACK_CHECK for {user.username}: {should_track}")
        return JsonResponse({'should_track': should_track})

    except Exception as e:
        print(f"ERROR in should_track_location_view for {user.username}: {e}")
        # In case of an error, default to not tracking to be safe
        return JsonResponse({'status': 'error', 'should_track': False}, status=500)
