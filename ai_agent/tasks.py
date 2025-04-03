from django.utils import timezone
from datetime import timedelta
from .models import Chat
from retell import Retell
from accounts.models import ApiCredential
from django.conf import settings
from retell_agent.models import RetellAgent
from automation.models import Lead
from subscription.models import UsageTracker
import traceback

def check_chat_status():
    """
    Task to check the status of pending chats and initiate calls if needed.
    This function is called by Django-Q scheduler.
    """
    try:
        print("[TASK] Starting check_chat_status task")
        chats = Chat.objects.filter(status='pending', updatedAt__lte=(timezone.now() - timedelta(minutes=10)))
        print(f"[TASK] Found {chats.count()} pending chats to process")
        
        results = {
            'processed': 0,
            'calls_made': 0,
            'errors': 0,
            'skipped': 0
        }
        
        for chat in chats:
            try:
                print(f"[TASK] Processing chat ID: {chat.id}, Phone: {chat.clientPhoneNumber}")
                
                # Skip chats without phone numbers
                if not chat.clientPhoneNumber:
                    print(f"[TASK] Skipping chat ID: {chat.id} - Missing phone number")
                    results['skipped'] += 1
                    continue
                
                # Get API credentials for this business
                try:
                    business = chat.business
                    retellAgent = RetellAgent.objects.get(business=business)
                    print(f"[TASK] Using business: {business.businessName}")
                except ApiCredential.DoesNotExist:
                    print(f"[TASK] No API credentials found for business ID: {chat.business.id}")
                    results['errors'] += 1
                    continue
                
                # Get lead information
                
                leads = Lead.objects.filter(phone_number=chat.clientPhoneNumber, business=business)
                for lead in leads:
                    print(f"[TASK] Found lead: {lead.name}")
                    if not lead:
                        print(f"[TASK] No lead found with phone number: {chat.clientPhoneNumber}")
                        results['errors'] += 1
                        continue
                    
                    # Process based on business settings
                    if business.useCall:
                        print(f"[TASK] Business uses call feature, attempting to make call")
                        
                        # Validate required credentials
                        if not retellAgent.agent_number:
                            print(f"[TASK] Missing voice agent number for business: {business.businessName}")
                            results['errors'] += 1
                            continue
                        
                        # Make the call
                        try:
                            client = Retell(api_key=settings.RETELL_API_KEY)
                            print(f"[TASK] Making call from {retellAgent.agent_number} to {lead.phone_number}")

                            if '+1' not in lead.phone_number and len(lead.phone_number) == 10:
                                lead.phone_number = '+1' + lead.phone_number
                            
                            call_response = client.call.create_phone_call(
                                from_number=retellAgent.agent_number,
                                to_number=lead.phone_number,
                                retell_llm_dynamic_variables={
                                    'name': lead.name,
                                    'service': lead.content
                                }
                            )
                            
                            # Update lead and chat status
                            lead.follow_up_call_sent = True
                            lead.follow_up_call_sent_at = timezone.now()
                            lead.save()
                            
                            chat.status = 'follow_up_call_sent'
                            chat.save()
                            
                            # Track usage for voice calls
                            UsageTracker.increment_metric(business, 'voice_calls')
                            
                            print(f"[TASK] Call successfully made, response ID: {call_response}")
                            results['calls_made'] += 1
                        except Exception as e:
                            print(f"[TASK] Error making call: {str(e)}")
                            print(traceback.format_exc())
                            results['errors'] += 1
                            continue
                    else:
                        print(f"[TASK] Business does not use call feature, skipping")
                    
                    results['processed'] += 1
                    print(f"[TASK] Successfully processed chat ID: {chat.id}")
                
            except Exception as chat_error:
                print(f"[TASK] Error processing chat ID: {chat.id}: {str(chat_error)}")
                print(traceback.format_exc())
                results['errors'] += 1
        
        print(f"[TASK] Completed check_chat_status task. Results: {results}")
        return results
        
    except Exception as e:
        print(f"[TASK] Fatal error in check_chat_status: {str(e)}")
        print(traceback.format_exc())
        return {
            'processed': 0,
            'calls_made': 0,
            'errors': 1,
            'skipped': 0,
            'fatal_error': str(e)
        }