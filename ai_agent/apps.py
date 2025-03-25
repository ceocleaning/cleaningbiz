from django.apps import AppConfig

class AiAgentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_agent'

    def ready(self):
        import ai_agent.signals

   