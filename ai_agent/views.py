from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

# Replace Gemini imports with OpenAI imports
from .openai_agent import OpenAIAgent

from accounts.models import Business, ApiCredential
from .models import AgentConfiguration, Chat, Messages


from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from twilio.twiml.messaging_response import MessagingResponse
from .openai_agent import OpenAIAgent
import os
import traceback
from openai import OpenAI

# Create your views here.



@login_required
def agent_config_detail(request):
    """View to see details of a specific agent configuration"""
    config = AgentConfiguration.objects.filter(business__user=request.user).first()
    business = Business.objects.filter(user=request.user).first()
    
    return render(request, 'ai_agent/agent_config_detail.html', {
        'config': config,
        'business': business
    })

@login_required
def agent_config_create(request):
    """View to create a new agent configuration"""
    # Get businesses the user owns
    business = request.user.business_set.first()
    
    if not business:
        messages.error(request, "You need to have a business registered before creating an AI Agent configuration.")
        return redirect('ai_agent:agent_config_list')
    
    # Check if configuration already exists for this business
    if AgentConfiguration.objects.filter(business=business).exists():
        messages.info(request, f"A configuration already exists for {business.businessName}. Redirecting to edit page.")
        return redirect('ai_agent:agent_config_edit', config_id=business.businessId)
    
    if request.method == 'POST':
        # Create new configuration
        config = AgentConfiguration.objects.create(
            business=business,
            agent_name=request.POST.get('agent_name', 'Sarah'),
            agent_role=request.POST.get('agent_role', 'virtual customer support and sales representative'),
            business_description=request.POST.get('business_description', ''),
            business_mission=request.POST.get('business_mission', ''),
            services=request.POST.get('services', ''),
            custom_instructions=request.POST.get('custom_instructions', ''),
            script=request.POST.get('script', '')
        )
        
        messages.success(request, f"Configuration for {business.businessName} created successfully.")
        return redirect('ai_agent:agent_config_detail', config_id=business.businessId)
    
    return render(request, 'ai_agent/agent_config_form.html', {
        'mode': 'create',
        'business': business
    })

@login_required
def agent_config_edit(request, config_id):
    """View to edit an existing agent configuration"""
    business = get_object_or_404(Business, businessId=config_id)
    
    # Check if user owns this business
    if business.user != request.user:
        messages.error(request, "You don't have permission to edit this configuration.")
        return redirect('ai_agent:agent_config')

    try:
        config = AgentConfiguration.objects.get(business=business)
    except AgentConfiguration.DoesNotExist:
        messages.error(request, "Configuration not found.")
        return redirect('ai_agent:agent_config')
    
    if request.method == 'POST':
        # Update configuration
        config.agent_name = request.POST.get('agent_name', config.agent_name)
        config.agent_role = request.POST.get('agent_role', config.agent_role)
        config.business_description = request.POST.get('business_description', config.business_description)
        config.business_mission = request.POST.get('business_mission', config.business_mission)
        config.services = request.POST.get('services', config.services)
        config.custom_instructions = request.POST.get('custom_instructions', config.custom_instructions)
        config.script = request.POST.get('script', config.script)
        config.save()
        
        messages.success(request, f"Configuration for {business.businessName} updated successfully.")
        return redirect('ai_agent:agent_config')
    
    return render(request, 'ai_agent/agent_config_form.html', {
        'config': config,
        'mode': 'edit'
    })

@login_required
@require_POST
def agent_config_delete(request):
    """View to delete an agent configuration"""
    business = get_object_or_404(Business, user=request.user)
    
    # Get the configuration for this business
    config = AgentConfiguration.objects.filter(business=business).first()
    
    if config:
        business_name = business.businessName
        config.delete()
        messages.success(request, f"Configuration for {business_name} deleted successfully.")
    else:
        messages.warning(request, "No configuration found to delete.")
    
    return redirect('ai_agent:agent_config')

@login_required
def agent_config_preview(request):
    """View to preview the system prompt generated from a configuration"""
    config = AgentConfiguration.objects.filter(business__user=request.user).first()
    
    # Check if user owns this business
    if not config:
        messages.error(request, "You don't have a configuration to preview.")
        return redirect('ai_agent:agent_config')
    
    # Generate the system prompt
    system_prompt = OpenAIAgent.get_dynamic_system_prompt(config.business.businessId)
   
    
    return render(request, 'ai_agent/agent_config_preview.html', {
        'config': config,
        'system_prompt': system_prompt
    })



# AI AGENT START


@csrf_exempt
def twilio_webhook(request, secretKey):
    print("Twilio webhook received")
    """Handle Twilio webhook requests for SMS interactions"""
    # Check if this is a POST request
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)
    
    # Get the incoming SMS data
    from_number = request.POST.get('From', '')
    body = request.POST.get('Body', '')
    to_number = request.POST.get('To', '')

    print(f"From: {from_number}, Body: {body}, To: {to_number}")
    
    # Initialize Twilio response
    twiml_response = MessagingResponse()
    
    try:
        # Clean the phone number (remove any + prefix)
        client_phone_number = from_number
        
        apiCred = ApiCredential.objects.filter(secretKey=secretKey).first()
        
        if not apiCred:
            twiml_response.message("Sorry, we couldn't process your request at this time.")
            return HttpResponse(str(twiml_response), content_type='text/xml')
        
        business = apiCred.business
        
        # Get or create a chat for this phone number
        chat = OpenAIAgent.get_or_create_chat(business.businessId, client_phone_number)
        
        if not chat:
            twiml_response.message("Sorry, we couldn't process your request at this time.")
            return HttpResponse(str(twiml_response), content_type='text/xml')
        
        # Save user message
        user_message = Messages.objects.create(
            chat=chat,
            role='user',
            message=body
        )
        
        # Get the system prompt
        system_prompt = OpenAIAgent.get_dynamic_system_prompt(business.businessId)
        if system_prompt == 0:
            # Use a default prompt if no configuration exists
            system_prompt = f"""You are Sarah, a virtual customer support and sales representative for {business.businessName}. You are speaking with a potential customer via SMS.
            Keep your responses concise and clear since this is an SMS conversation.
            Your primary goals are to:
            1. Answer questions about cleaning services
            2. Collect customer details (name, phone, email, address)
            3. Gather property details (square footage, bedrooms, bathrooms)
            4. Provide service options and pricing
            5. Schedule appointments within business hours (9 AM - 5 PM Central Time)
            6. Send booking confirmations
            
            Follow this conversation flow: greeting → gathering details → service selection → scheduling → confirmation
            
            Use tools when appropriate for checking availability and booking appointments.
            
            Always be friendly, professional, and helpful."""
        
        # Get all messages for this chat
        messages = OpenAIAgent.get_chat_messages(client_phone_number)
        
        # Format messages for OpenAI
        formatted_messages = OpenAIAgent.format_messages_for_openai(messages, system_prompt)
        
        # Call OpenAI API
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=formatted_messages,
                temperature=0.5,
                max_tokens=512,  # Shorter for SMS
                tools=OpenAIAgent.get_openai_tools()
            )
            
            # Process the response
            ai_response_text = OpenAIAgent.process_ai_response(response.choices[0].message, client_phone_number)
            
            # Save the assistant message
            assistant_message = Messages.objects.create(
                chat=chat,
                role='assistant',
                message=ai_response_text
            )
            
            # Send the AI response back via SMS
            # Truncate if necessary to fit SMS length limits
            if len(ai_response_text) > 1500:
                ai_response_text = ai_response_text[:1497] + "..."
                
            twiml_response.message(ai_response_text)
            
        except Exception as e:
            print(f"Error calling OpenAI API: {str(e)}")
            traceback.print_exc()
            twiml_response.message("Sorry, we're experiencing technical difficulties. Please try again later.")
        
        # Return the TwiML response
        return HttpResponse(str(twiml_response), content_type='text/xml')
        
    except Exception as e:
        print(f"Error in Twilio webhook: {str(e)}")
        traceback.print_exc()
        
        # Send a generic error message
        twiml_response.message("Sorry, we encountered an error processing your request. Please try again later.")
        return HttpResponse(str(twiml_response), content_type='text/xml')
