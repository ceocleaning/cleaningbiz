from email import message
from accounts.models import ApiCredential
from ai_agent.models import AgentConfiguration, Messages, Chat
from retell_agent.models import RetellAgent
from retell import Retell
from .models import Lead
from django.utils import timezone
from django.conf import settings

def send_call_to_lead(lead_id):
    try:
        # Get the lead object from the database using the ID
        lead = Lead.objects.get(id=lead_id)
        chat = Chat.objects.get(lead=lead)
        messages = Messages.objects.filter(chat=chat, is_first_message=True)
        retellAgent = RetellAgent.objects.get(business=lead.business)

        if not lead.is_response_received and retellAgent.agent_number:
            
            client = Retell(api_key=settings.RETELL_API_KEY)
            call_response = client.call.create_phone_call(
                from_number=retellAgent.agent_number,
                to_number=lead.phone_number,
                retell_llm_dynamic_variables={
                    'name': lead.name,
                    'service': lead.content
                }
            )
            lead.is_call_sent = True
            lead.call_sent_at = timezone.now()
            lead.save()
            print(call_response)
        
        return 0

    except Lead.DoesNotExist:
        return -1

    except Exception as e:
        print(f"Error making call: {e}")
        return -1
