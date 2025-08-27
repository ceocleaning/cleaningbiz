from email import message
from accounts.models import ApiCredential
from ai_agent.models import AgentConfiguration, Messages, Chat
from retell_agent.models import RetellAgent
from subscription.models import BusinessSubscription, SubscriptionPlan, UsageTracker
from retell import Retell
from .models import Lead
from django.utils import timezone
from django.conf import settings


def send_call_to_lead(lead_id):
    try:
        # Get the lead object from the database using the ID
        lead = Lead.objects.get(id=lead_id)
        chat = Chat.objects.get(lead=lead)
        retellAgent = RetellAgent.objects.get(business=lead.business)

        lead_details = f"Here are the details about the lead:\nName: {lead.name}\nPhone: {lead.phone_number}\nEmail: {lead.email if lead.email else 'Not provided'}\nAddress: {lead.address1 if lead.address1 else 'Not provided'}\nCity: {lead.city if lead.city else 'Not provided'}\nState: {lead.state if lead.state else 'Not provided'}\nZip Code: {lead.zipCode if lead.zipCode else 'Not provided'}\nProposed Start Time: {lead.proposed_start_datetime.strftime('%B %d, %Y at %I:%M %p') if lead.proposed_start_datetime else 'Not provided'}\nNotes: {lead.notes if lead.notes else 'No additional notes'}"

        if not lead.is_response_received and retellAgent.agent_number:
            client = Retell(api_key=settings.RETELL_API_KEY)
            call_response = client.call.create_phone_call(
                from_number=retellAgent.agent_number,
                to_number=lead.phone_number,
                override_agent_id=retellAgent.agent_id,
                retell_llm_dynamic_variables={
                    'name': lead.name,
                    'details': lead_details,
                    'service': 'cleaning'
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
