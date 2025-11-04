from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import timezone
import json
import threading

from business.models import Business
from .models import Chat, Message, AgentConfig
from twilio.twiml.messaging_response import MessagingResponse
from .utils import process_sms_with_langchain, process_web_chat_with_langchain

@login_required
def agent_dashboard(request):
    """
    Unified dashboard for managing and testing AI agents for a business.
    """
    business = request.user.business
    
    # Get or create agent config
    agent_config = AgentConfig.objects.filter(business=business).first()
    if not agent_config:
        agent_config = AgentConfig.objects.create(
            business=business,
            name=f"{business.name} Assistant",
            is_active=True
        )
    
    # Get recent chats
    chats = Chat.objects.filter(business=business).order_by('-updated_at')[:10]
    
    # Generate the system prompt to display
    from .langchain_agent import LangChainAgent
    try:
        agent = LangChainAgent(business_id=str(business.id))
        system_prompt = agent._get_system_prompt()
    except Exception as e:
        system_prompt = f"Error generating system prompt: {str(e)}"
    
    if request.method == 'POST':
        # Handle agent config update
        agent_config.name = request.POST.get('name', agent_config.name)
        agent_config.prompt = request.POST.get('prompt', '')
        agent_config.save()
        
        return redirect('ai_agent:dashboard')
    
    context = {
        'business': business,
        'agent_config': agent_config,
        'chats': chats,
        'system_prompt': system_prompt,
    }
    
    return render(request, 'ai_agent/ai_agent_unified.html', context)

@login_required
def chat_list(request):
    """
    List all chats for a business.
    """
    business = request.user.business
    chats = Chat.objects.filter(business=business).order_by('-updated_at')
    
    context = {
        'business': business,
        'chats': chats,
    }
    
    return render(request, 'ai_agent/chat_list.html', context)

@login_required
def chat_detail(request, chat_id):
    """
    View details of a chat including all messages.
    """
    business = request.user.business
    chat = get_object_or_404(Chat, id=chat_id, business=business)
    chat_messages = chat.messages.all().order_by('created_at')
    
    context = {
        'business': business,
        'chat': chat,
        'chat_messages': chat_messages,
    }
    
    return render(request, 'ai_agent/chat_detail.html', context)

@csrf_exempt
@require_POST
def process_message(request):
    """
    API endpoint for processing messages from clients.
    This can be called from a web chat interface or SMS webhook.
    """
    try:
        print("[DEBUG] Starting process_message view")
        # Parse request body as JSON
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            print("[DEBUG] Invalid JSON in request body")
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        
        # Extract required fields
        business_id = data.get('business_id')
        message = data.get('message')
        phone_number = data.get('phone_number')
        session_key = data.get('session_key')
        
        print(f"[DEBUG] Received message: '{message}' for business_id: {business_id}")
        
        # Validate required fields
        if not business_id or not message or (not phone_number and not session_key):
            print("[DEBUG] Missing required fields")
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields: business_id, message, and either phone_number or session_key'
            }, status=400)
        
        # Get business
        try:
            business = Business.objects.get(id=business_id)
            print(f"[DEBUG] Found business: {business.name} (ID: {business.id})")
        except Business.DoesNotExist:
            print(f"[DEBUG] Business with ID {business_id} not found")
            return JsonResponse({
                'success': False,
                'error': f'Business with ID {business_id} not found'
            }, status=404)
        
        # Process the message using LangChain agent
        if phone_number:
            print("[DEBUG] Processing SMS message")
            response = process_sms_with_langchain(business_id, phone_number, message)
        else:
            print("[DEBUG] Processing web chat message")
            response = process_web_chat_with_langchain(business_id, session_key, message)
        
        # Get the chat ID
        chat = None
        if phone_number:
            chat = Chat.objects.filter(business_id=business_id, phone_number=phone_number).first()
        elif session_key:
            chat = Chat.objects.filter(business_id=business_id, session_key=session_key).first()
        
        print(f"[DEBUG] Chat ID: {chat.id if chat else None}")
        
        return JsonResponse({
            'success': True,
            'response': response,
            'chat_id': chat.id if chat else None
        })
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"[DEBUG] Error processing message: {str(e)}")
        print(f"[DEBUG] Traceback: {error_traceback}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
@require_POST
def twilio_webhook(request, business_id):
    """
    Webhook for receiving SMS messages from Twilio.
    Immediately acknowledges receipt with an empty TwiML response,
    then processes the message in a background thread.
    """
    # Extract message data from Twilio webhook
    from_number = request.POST.get('From')
    body = request.POST.get('Body')
    to_number = request.POST.get('To')
    
    # Immediately return an empty TwiML response to acknowledge receipt
    empty_response = MessagingResponse()
    
    # Start processing in background only if we have the required parameters
    if from_number and body and to_number:
        # Create a copy of the data we need for background processing
        process_data = {
            'business_id': business_id,
            'from_number': from_number,
            'body': body,
            'to_number': to_number
        }
        
        # Start background thread to process the message
        thread = threading.Thread(
            target=process_twilio_message_in_background,
            args=(process_data,)
        )
        thread.daemon = True  # Allow the thread to exit when main thread exits
        thread.start()
    
    # Return the empty response immediately
    return HttpResponse(str(empty_response), content_type='text/xml')


def process_twilio_message_in_background(data):
    """
    Process Twilio message in a background thread and send response via Twilio API.
    
    Args:
        data: Dictionary containing business_id, from_number, body, and to_number
    """
    try:
        business_id = data['business_id']
        from_number = data['from_number']
        body = data['body']
        to_number = data['to_number']
        
        try:
            business = Business.objects.get(id=business_id)
            if not business:
                print(f"No business found for business_id {business_id}")
                return
        except Exception as e:
            print(f"Error finding business: {str(e)}")
            return
        
        # Process the message
        response = process_sms_with_langchain(business.id, from_number, body)
        
        # Send the response back via Twilio API
        send_twilio_response(business, to_number, from_number, response)
        
    except Exception as e:
        print(f"Error in background processing of Twilio message: {e}")


def send_twilio_response(business, from_number, to_number, message):
    """
    Send SMS response using Twilio API directly instead of TwiML.
    
    Args:
        business: Business object
        from_number: Twilio number to send from
        to_number: Customer number to send to
        message: Message content
    """
    try:
        # Import Twilio client here to avoid circular imports
        from twilio.rest import Client
        
        business_config = business.businessconfiguration
        account_sid = business_config.twilio_sid
        auth_token = business_config.twilio_auth_token
        
        # Initialize Twilio client
        client = Client(account_sid, auth_token)
        
        # Send message
        client.messages.create(
            body=message,
            from_=from_number,
            to=to_number
        )
        
    except Exception as e:
        print(f"Error sending Twilio response: {e}")




@require_GET
def chat_widget(request, business_id):
    """
    Render the chat widget for embedding on a website.
    """
    business = get_object_or_404(Business, id=business_id)
    
    context = {
        'business': business,
    }
    
    return render(request, 'ai_agent/chat_widget.html', context)