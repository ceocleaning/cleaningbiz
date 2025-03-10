from accounts.models import ApiCredential
from retell import Retell
from .models import Lead


def send_call_to_lead(lead_id):
    print(f"Sending call to lead with ID: {lead_id}...")
    try:
        # Get the lead object from the database using the ID
        lead = Lead.objects.get(id=lead_id)
        
        # apiCreds = ApiCredential.objects.get(business=lead.business)
        # client = Retell(api_key=apiCreds.retellAPIKey)
        # call_response = client.call.create_phone_call(
        #     from_number=apiCreds.voiceAgentNumber,
        #     to_number=lead.phone_number,
        #     retell_llm_dynamic_variables={
        #         'name': lead.name,
        #         'service': lead.content
        #     },
        # )
        # print(call_response)
        print(f"Call sent successfully to {lead.name}!")

    except Lead.DoesNotExist:
        print(f"Error: Lead with ID {lead_id} does not exist")
    except Exception as e:
        print(f"Error making call: {e}")