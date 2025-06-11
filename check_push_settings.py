from django.conf import settings

print("--- Checking PUSH_NOTIFICATIONS_SETTINGS from Django Shell ---")

push_settings_from_s_object = None # Use a different variable name to avoid confusion with 'settings' module

if hasattr(settings, 'PUSH_NOTIFICATIONS_SETTINGS'):
    push_settings_from_s_object = settings.PUSH_NOTIFICATIONS_SETTINGS
    print(f"DEBUG_SHELL: Type of settings.PUSH_NOTIFICATIONS_SETTINGS: {type(push_settings_from_s_object)}")
    print(f"DEBUG_SHELL: Content of settings.PUSH_NOTIFICATIONS_SETTINGS: {push_settings_from_s_object}") # <<< VERY IMPORTANT LINE
    
    if isinstance(push_settings_from_s_object, dict):
        private_key = push_settings_from_s_object.get("VAPID_PRIVATE_KEY") # Exact key name
        public_key = push_settings_from_s_object.get("VAPID_PUBLIC_KEY")   # Exact key name
        wp_claims = push_settings_from_s_object.get("WP_CLAIMS")           # Exact key name
        
        print(f"DEBUG_SHELL: VAPID_PRIVATE_KEY from dict (first 20 chars): {str(private_key)[:20] if private_key else 'KEY_NOT_FOUND_IN_DICT_or_None_Value'}")
        print(f"DEBUG_SHELL: VAPID_PUBLIC_KEY from dict (first 20 chars): {str(public_key)[:20] if public_key else 'KEY_NOT_FOUND_IN_DICT_or_None_Value'}")
        print(f"DEBUG_SHELL: WP_CLAIMS from dict: {wp_claims}")
    else:
        print("DEBUG_SHELL: settings.PUSH_NOTIFICATIONS_SETTINGS was found, but it is not a dictionary.")
else:
    print("DEBUG_SHELL: settings.PUSH_NOTIFICATIONS_SETTINGS attribute does not exist on the settings object.")
    
print("--- Finished PUSH_NOTIFICATIONS_SETTINGS check ---")
