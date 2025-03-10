from accounts.models import ApiCredential
from retell import Retell


def send_call_to_lead(lead):
    print("Sending call to lead...")
    try:
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
        print("Call sent successfully!")

    except Exception as e:
        print(f"Error making call: {e}")