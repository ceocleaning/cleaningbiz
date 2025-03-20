from django.utils import timezone
from datetime import timedelta
from .models import Chat
from retell import Retell
from accounts.models import ApiCredential
from automation.models import Lead




def check_chat_status():
    chats = Chat.objects.filter(status='pending', updatedAt__lte=(timezone.now() - timedelta(minutes=2)))
    for chat in chats:
        apiCreds = ApiCredential.objects.get(business=chat.business)
        business = apiCreds.business
        lead = Lead.objects.get(phone_number=chat.clientPhoneNumber)

        if business.useCall:
            if not apiCreds.retellAPIKey or not apiCreds.voiceAgentNumber:
                return -1
            
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

            chat.status = 'call_sent'
            chat.save()

            return 1 

        return 0