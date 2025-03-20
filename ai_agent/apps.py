from django.apps import AppConfig


class AiAgentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_agent'

    def ready(self):
        """This function runs when Django starts"""
        from ai_agent.tasks import check_chat_status  # Import the function
        from django_q.tasks import schedule
        from django_q.models import Schedule
        
        # Check if the schedule already exists
        if not Schedule.objects.filter(func="ai_agent.tasks.check_chat_status").exists():
            # Schedule the function to run every 2 minutes
            schedule(
                "ai_agent.tasks.check_chat_status",  # Replace with the actual function path
                schedule_type=Schedule.MINUTES,
                minutes=2,
                repeats=-1,  # Run indefinitely
            )