from django.apps import AppConfig


class AutomationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'automation'

    def ready(self):
        import automation.signals  # Import the signals module
        # Make sure Django knows about our template tags
        import importlib
        try:
            importlib.import_module('automation.templatetags.split_filter')
            importlib.import_module('automation.templatetags.json_format_filter')
        except ImportError:
            pass