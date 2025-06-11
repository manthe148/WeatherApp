# /srv/radar_site_prod/accounts/apps.py
from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts' # This should match your app's directory name

    def ready(self):
        # --- ADD THESE PRINT STATEMENTS FOR DEBUGGING ---
        print("ACCOUNTS_APP_CONFIG_DEBUG: AccountsConfig.ready() method CALLED.")
        try:
            import accounts.signals # This line is what connects your signals
            print("ACCOUNTS_APP_CONFIG_DEBUG: accounts.signals imported successfully.")
        except ImportError as e:
            print(f"ACCOUNTS_APP_CONFIG_DEBUG: FAILED to import accounts.signals: {e}")
        except Exception as e_general:
            print(f"ACCOUNTS_APP_CONFIG_DEBUG: UNEXPECTED error importing accounts.signals: {e_general}")
        # --- END DEBUG PRINTS ---
