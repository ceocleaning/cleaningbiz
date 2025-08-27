from django.apps import AppConfig


class RetellAgentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'retell_agent'

    def ready(self):
        import retell_agent.signals
