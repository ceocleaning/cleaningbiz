from django.apps import AppConfig


class AutomationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'automation'

    def ready(self):
        import automation.signals  # Import the signals module
        # Make sure Django knows about our template tags
        from django.template import Library
        import automation.templatetags.automation_filters