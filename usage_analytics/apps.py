from django.apps import AppConfig


class UsageAnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'usage_analytics'
    
    def ready(self):
        """Import signals when the app is ready."""
        import usage_analytics.signals