from email import message
from accounts.models import ApiCredential
from ai_agent.models import AgentConfiguration, Messages, Chat
from retell import Retell
from .models import Lead
from django.utils import timezone

def send_call_to_lead(lead_id):
    try:
        # Get the lead object from the database using the ID
        lead = Lead.objects.get(id=lead_id)
        chat = Chat.objects.get(lead=lead)
        messages = Messages.objects.filter(chat=chat, is_first_message=True)
        if not lead.is_response_received:
            apiCreds = ApiCredential.objects.get(business=lead.business)

            client = Retell(api_key=apiCreds.retellAPIKey)
            call_response = client.call.create_phone_call(
                from_number=apiCreds.voiceAgentNumber,
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
