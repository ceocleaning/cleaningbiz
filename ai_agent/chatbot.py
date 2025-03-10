from dotenv import load_dotenv
import os
import json
import uuid
import logging
import re
from datetime import datetime, timedelta
import pytz

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404

from accounts.models import Business
from bookings.models import Booking
from .models import Chat, Messages, AgentConfiguration
from .api_views import check_availability, book_appointment, get_current_time_in_chicago

import google.generativeai as genai

load_dotenv()


# Initialize Google Gemini AI
genai.configure(api_key=os.getenv('GEMENI_API'))
model = genai.GenerativeModel('gemini-2.0-flash')


# Define available tools
tools = {
    'check_availability': check_availability,
    'bookAppointment': book_appointment,
    'current_time': get_current_time_in_chicago
}



def get_dynamic_system_prompt(business_id):
    """
    Generate a dynamic system prompt based on the business and agent configuration
    stored in the database. Falls back to default prompt if no configuration exists.
    """
    try:
        # Get the business configuration
        config = AgentConfiguration.objects.get(business__businessId=business_id)
        business = Business.objects.get(businessId=business_id)
        
        # Build the dynamic system prompt
        prompt = f"""
        ## **Role of the AI Voice Agent**
        You are {config.agent_name}, acting as a {config.agent_role} for {business.businessName}. You efficiently handle inbound and outbound calls to:

        - Greet and engage potential customers professionally
        - Confirm interest in cleaning services
        - Gather essential customer details (name, phone number, email, and address)
        - Collect property details (square footage, bedrooms, bathrooms)
        - Provide service options and pricing transparently
        - Offer discounts when necessary
        - Schedule and confirm cleaning appointments
        - Send booking confirmation and invoice links via email or SMS

        The AI ensures a seamless, professional, and persuasive booking process, helping {business.businessName} secure more appointments while maintaining excellent customer service.

        ---

        ## **Who Are {business.businessName}?**
        {config.business_description or f"{business.businessName} is a leading professional cleaning service provider based in {business.businessCity}, {business.businessState}. They specialize in top-quality residential and commercial cleaning services tailored to meet each client's unique needs."}

        ### {business.businessName}'s Mission:
        {config.business_mission or "- Deliver high-quality, reliable, and professional cleaning services\n- Ensure a clean and healthy environment for clients\n- Guarantee 100% customer satisfaction with every service"}

        ### Services Offered:
        {config.services or "- Regular Cleaning: Best for basic home maintenance cleaning\n- Deep Cleaning: Ideal for thorough cleaning, great for first-time or seasonal cleanings\n- Commercial Cleaning: Tailored for offices and business spaces"}


        You have access to the following tools to help with the booking process:

        1. check_availability: Check if a specific date and time is available for booking
        - Input: 
                - A date and time string (e.g., "Tomorrow at 2 PM", "March 15, 2025 at 10 AM")
                - Business Object
        - Output: Availability status

        2. bookAppointment: Book an appointment in the system
        - Input: 
                - Customer details as a dictionary
                - Business Object
        - Output: Booking confirmation and ID

        3. current_time: Get the current time in Chicago timezone
        - Input: None
        - Output: Current time in Chicago timezone

        When you need to use a tool, use one of the following formats:
        
        Format 1 (preferred):
        <tool>tool_name(parameters)</tool>

        Format 2 (alternative):
        ```tool_code tool_name(parameters) ```

        For example:
        <tool>check_availability(Tomorrow at 2 PM)</tool>
        OR
        ```tool_code check_availability(Tomorrow at 2 PM) ```

        <tool>bookAppointment()</tool>
        OR
        ```tool_code bookAppointment() ```

        <tool>current_time()</tool>
        OR
        ```tool_code current_time() ```

        Be friendly, professional, and helpful. Follow the conversation flow carefully and wait for user responses before moving to the next step.

        Maintain a conversational tone and allow pauses for natural interaction.

        Always include "AM" or "PM" when mentioning time (e.g., "Three thirty PM").
        Never say "O'Clock." Instead, say "One PM."

        ##Script - AI will follow this Script
        {config.script or ""}
        """
        
        # Add any custom instructions if available
        if config.custom_instructions:
            prompt += f"\n\n## **Additional Instructions**\n{config.custom_instructions}"
        
        return prompt
        
    except Exception as e:
        logger.error(f"Error generating dynamic system prompt: {str(e)}")
        # Return a basic default prompt if anything goes wrong
        return "You are an AI assistant for a cleaning business. Help customers book appointments and answer their questions about services."



def execute_tool_call(tool_call, client_phone_number):
    """Execute a tool call and return the result"""
    # Extract tool name and parameters using regex
    tool_match = re.match(r'<tool>(\w+)\((.*)\)</tool>', tool_call)
    
    if not tool_match:
        return "Error: Invalid tool call format"
    
    tool_name = tool_match.group(1)
    tool_params_str = tool_match.group(2)
    
    # Check if the tool exists
    if tool_name not in tools:
        return f"Error: Tool '{tool_name}' not found"
    
    # Get the business for this chat
    try:
        chat = Chat.objects.get(clientPhoneNumber=client_phone_number)
        business = chat.business
        
        # Execute the tool with the provided parameters
        if tool_name == 'check_availability':
            # For check_availability, we need to pass the business and date string
            result = tools['check_availability'](business, tool_params_str)
            return json.dumps(result, default=str)
            
        elif tool_name == 'bookAppointment':
            # For bookAppointment, we need to extract conversation data and pass with business
            chat_messages = Messages.objects.filter(chat=chat).order_by('createdAt')
            customer_data = extract_conversation_summary(chat_messages)
            result = tools['bookAppointment'](business, customer_data)
            return json.dumps(result, default=str)
            
        elif tool_name == 'current_time':
            # current_time doesn't need parameters
            result = tools['current_time']()
            return result
            
        else:
            # Default handling for unknown tools
            return f"Error: Tool '{tool_name}' implementation not found"
            
    except Chat.DoesNotExist:
        return "Error: Chat not found"
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {str(e)}")
        return f"Error executing tool {tool_name}: {str(e)}"


def process_ai_response(response_text, client_phone_number, formatted_messages=None):
    """Process the AI response to execute any tool calls"""
    # Check if the response contains any tool calls in <tool> format
    tool_pattern = r'<tool>(.*?)</tool>'
    tool_calls = re.findall(tool_pattern, response_text)
    
    # Also check for tool_code format
    tool_code_pattern = r'```tool_code\s+(\w+)\(([^)]*)\)\s+```'
    tool_code_calls = re.findall(tool_code_pattern, response_text)
    
    # If no tool calls found in either format, return the original response
    if not tool_calls and not tool_code_calls:
        return response_text
    
    # Process each tool call in <tool> format and replace with the result
    for tool_call in tool_calls:
        full_tool_call = f"<tool>{tool_call}</tool>"
        tool_result = execute_tool_call(full_tool_call, client_phone_number)
        
        # Replace the tool call with the result
        response_text = response_text.replace(full_tool_call, f"\n\nTool Result: {tool_result}\n\n")
    
    # Process each tool call in tool_code format and replace with the result
    for tool_name, tool_params in tool_code_calls:
        full_tool_call = f"```tool_code {tool_name}({tool_params}) ```"
        # Convert to <tool> format for execute_tool_call
        tool_call_converted = f"<tool>{tool_name}({tool_params})</tool>"
        tool_result = execute_tool_call(tool_call_converted, client_phone_number)
        
        # Replace the tool call with the result
        response_text = response_text.replace(full_tool_call, f"\n\nTool Result: {tool_result}\n\n")
    
    # If formatted_messages is provided, add the tool result and generate a new response
    if formatted_messages and (tool_calls or tool_code_calls):
        # Add all tool results to formatted_messages
        formatted_messages.append({"role": "model", "parts": [{"text": f"Tool Result: {tool_result}"}]})

        # Generate response from the model
        response = model.generate_content(
            formatted_messages,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=1024,
                top_p=0.95,
                top_k=40,
            )
        )
        
        return response.text
    
    return response_text


def get_ai_response(messages, business_id, client_phone_number):
    """
    Get response from Google Gemini AI with tool calling capabilities
    """
    try:
        # Get the system prompt (now dynamic based on business configuration)
        system_prompt = get_dynamic_system_prompt(business_id)
        
        # Format messages for the model
        formatted_messages = []
        
        # Add system prompt as the first message
        formatted_messages.append({"role": "model", "parts": [{"text": system_prompt}]})
        
        # Add user and model messages
        for msg in messages:
            role = "user" if msg.role == "user" else "model"
            formatted_messages.append({"role": role, "parts": [{"text": msg.message}]})
        
        # Generate response from the model
        response = model.generate_content(
            formatted_messages,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=1024,
                top_p=0.95,
                top_k=40,
            )
        )
        
        # Process the response to execute any tool calls
        processed_response = process_ai_response(response.text, client_phone_number, formatted_messages)
        
        return processed_response
    except Exception as e:
        logger.error(f"Error getting AI response: {str(e)}")
        return "I'm sorry, I'm having trouble processing your request right now. Please try again later."


def extract_conversation_summary(chat_history):
    """
    Extract key information from the conversation history for booking purposes using Gemini LLM.
    Returns a structured JSON object with customer and appointment details.
    """
    print("\n===== EXTRACTING CONVERSATION SUMMARY USING GEMINI LLM =====\n")
    
    # Initialize empty summary structure
    summary = {
        'firstName': '',
        'lastName': '',
        'email': '',
        'phoneNumber': '',
        'address': '',
        'city': '',
        'state': '',
        'zipCode': '',
        'squareFeet': '',
        'bedrooms': '',
        'bathrooms': '',
        'serviceType': '',
        'appointmentDateTime': '',
        'additionalNotes': '',
        'detailSummary': '',
        "addonDishes": '',
        "addonLaundryLoads": '',
        "addonWindowCleaning": '',
        "addonPetsCleaning": '',
        "addonFridgeCleaning": '',
        "addonOvenCleaning": '',
        "addonBaseboard": '',
        "addonBlinds": '',
        "addonGreenCleaning": '',
        "addonCabinetsCleaning": '',
        "addonPatioSweeping": '',
        "addonGarageSweeping": ''
    }
    
    # Join all messages into a single text for analysis
    full_conversation = ' '.join([msg.message for msg in chat_history])
    print(f"Analyzing conversation with {len(chat_history)} messages")
    
    # Create a prompt for Gemini to extract the information
    extraction_prompt = f"""
    You are an AI assistant tasked with extracting specific information from a customer conversation with CEO Cleaners.
    Please analyze the following conversation and extract the information in a structured JSON format.
    
    Conversation:
    {full_conversation}
    
    Extract the following information and respond ONLY with a valid JSON object with these keys:
    - firstName: Customer's first name
    - lastName: Customer's last name
    - email: Customer's email address
    - phoneNumber: Customer's phone number
    - address: Street address (just the street part, no city/state/zip)
    - city: City name
    - state: Two-letter state code (e.g., TX for Texas)
    - zipCode: 5-digit or 9-digit zip code
    - squareFeet: Square footage of the property as a numeric string
    - bedrooms: Number of bedrooms as a numeric string
    - bathrooms: Number of bathrooms as a numeric string
    - serviceType: Type of service requested (e.g., "regular cleaning", "deep cleaning", "move-in")
    - appointmentDateTime: Appointment date and time in ANY format mentioned in the conversation
    - additionalNotes: Any special requests or notes
    - addonDishes: Quantity of Dishes Addon
    - addonLaundryLoads: Quantity of Laundry Loads Addon
    - addonWindowCleaning: Quantity of Window Cleaning Addon
    - addonPetsCleaning: Quantity of Pets Cleaning Addon
    - addonFridgeCleaning: Quantity of Fridge Cleaning Addon
    - addonOvenCleaning: Quantity of Oven Cleaning Addon
    - addonBaseboard: Quantity of Baseboard Addon
    - addonBlinds: Quantity of Blinds Addon
    - addonGreenCleaning: Quantity of Green Cleaning Addon
    - addonCabinetsCleaning: Quantity of Cabinets Cleaning Addon
    - addonPatioSweeping: Quantity of Patio Sweeping Addon
    - addonGarageSweeping: Quantity of Garage Sweeping Addon
    
    Use empty strings for any information that is not present in the conversation.
    
    IMPORTANT INSTRUCTIONS FOR APPOINTMENT DATE AND TIME:
    - Extract the appointment date and time in EXACTLY the format mentioned in the conversation
    - Look for ANY mention of scheduling, booking, or appointments
    - Handle relative times like "tomorrow at 10 AM", "next Tuesday at 2 PM", "this Friday afternoon"
    - Handle specific dates like "March 15th at 2 PM", "3/15/2025 at 14:00"
    - If only a day of week is mentioned (e.g., "Monday"), assume it's the next occurrence of that day
    - If only a time is mentioned (e.g., "3 PM"), assume it's for the next business day
    - The current date and time is {get_current_time_in_chicago()}
    - Always include both the date and time in your extracted appointmentDateTime field
    - Do not convert to UTC - return the exact text as mentioned in the conversation
    """
    
    try:
        # Call Gemini API to extract information
        extraction_response = model.generate_content(
            extraction_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,  # Low temperature for more deterministic results
                max_output_tokens=1024,
            )
        )
        
        # Parse the response as JSON
        try:
            # Extract JSON from the response text
            response_text = extraction_response.text.strip()
            
            # Handle case where response might have markdown code block formatting
            if response_text.startswith('```json'):
                response_text = response_text.split('```json', 1)[1]
            if response_text.endswith('```'):
                response_text = response_text.rsplit('```', 1)[0]
                
            response_text = response_text.strip()
            extracted_data = json.loads(response_text)
            
            print("Successfully extracted data using Gemini LLM")
            
            # Update summary with extracted data
            for key in summary.keys():
                if key in extracted_data and extracted_data[key]:
                    summary[key] = extracted_data[key]
                    print(f"Extracted {key}: {summary[key]}")
                else:
                    print(f"No {key} extracted")
            
            # Convert appointment date and time to UTC if present
            if summary['appointmentDateTime']:
                try:
                    local_datetime_str = summary['appointmentDateTime']
                    print(f"Extracted appointment text: {local_datetime_str}")
                    
                    # Create a second prompt to parse the datetime string
                    datetime_parsing_prompt = f"""
                    You are an AI assistant that specializes in parsing date and time information.
                    
                    The current date is: {datetime.now().strftime('%Y-%m-%d')}
                    The current time is: {datetime.now().strftime('%H:%M')}
                    
                    Please parse the following appointment text and convert it to a specific date and time:
                    "{local_datetime_str}"
                    
                    If the text mentions a relative time like "tomorrow" or "next Tuesday", calculate the actual date.
                    If only a day of week is mentioned, assume it's the next occurrence of that day.
                    If only a time is mentioned, assume it's for today or the next business day.
                    
                    Respond ONLY with a valid JSON object with these keys:
                    - year: The 4-digit year (e.g., 2025)
                    - month: The month as a number (1-12)
                    - day: The day of month (1-31)
                    - hour: The hour in 24-hour format (0-23)
                    - minute: The minute (0-59)
                    - period: "AM" or "PM" if specified
                    
                    If any component is not specified or cannot be determined, make a reasonable assumption based on context.
                    """
                    
                    # Call Gemini API to parse the datetime
                    datetime_parsing_response = model.generate_content(
                        datetime_parsing_prompt,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.1,
                            max_output_tokens=512,
                        )
                    )
                    
                    # Extract JSON from the response text
                    parsing_response_text = datetime_parsing_response.text.strip()
                    
                    # Handle case where response might have markdown code block formatting
                    if parsing_response_text.startswith('```json'):
                        parsing_response_text = parsing_response_text.split('```json', 1)[1]
                    if parsing_response_text.endswith('```'):
                        parsing_response_text = parsing_response_text.rsplit('```', 1)[0]
                    
                    parsing_response_text = parsing_response_text.strip()
                    datetime_components = json.loads(parsing_response_text)
                    
                    print(f"Parsed datetime components: {datetime_components}")
                    
                    # Construct datetime object from components
                    year = int(datetime_components.get('year', datetime.now().year))
                    month = int(datetime_components.get('month', datetime.now().month))
                    day = int(datetime_components.get('day', datetime.now().day))
                    hour = int(datetime_components.get('hour', 12))
                    minute = int(datetime_components.get('minute', 0))
                    
                    # Adjust for AM/PM if period is provided
                    period = datetime_components.get('period', '')
                    if period.upper() == 'PM' and hour < 12:
                        hour += 12
                    elif period.upper() == 'AM' and hour == 12:
                        hour = 0
                    
                    # Create datetime object
                    local_dt = datetime(year, month, day, hour, minute)
                    print(f"Constructed local datetime: {local_dt}")
                    
                    # Set the timezone to Chicago
                    chicago_tz = pytz.timezone('America/Chicago')
                    local_dt_with_tz = chicago_tz.localize(local_dt)
                    
                    # Convert to UTC
                    utc_dt = local_dt_with_tz.astimezone(pytz.UTC)
                    
                    # Format as ISO string
                    summary['appointmentDateTime'] = utc_dt.isoformat()
                    print(f"Converted to UTC: {summary['appointmentDateTime']}")
                    
                except Exception as e:
                    logger.error(f"Error converting datetime to UTC: {str(e)}")
                    print(f"Error converting datetime: {str(e)}")
                    print(f"Will try fallback datetime parsing methods")
                    
                    # Fallback method: Try to use dateutil parser
                    try:
                        from dateutil import parser as date_parser
                        
                        # Replace common relative time expressions
                        today = datetime.now()
                        text = local_datetime_str.lower()
                        
                        # Handle common relative time expressions
                        if 'tomorrow' in text:
                            base_date = today + timedelta(days=1)
                        elif 'next week' in text:
                            base_date = today + timedelta(days=7)
                        elif any(day in text for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']):
                            # Find the mentioned day of week
                            days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                            for i, day in enumerate(days):
                                if day in text:
                                    # Calculate days until the next occurrence of this day
                                    current_weekday = today.weekday()
                                    days_ahead = i - current_weekday
                                    if days_ahead <= 0:  # Target day already happened this week
                                        days_ahead += 7
                                    base_date = today + timedelta(days=days_ahead)
                                    break
                        else:
                            base_date = today
                        
                        # Try to parse the time portion
                        parsed_dt = date_parser.parse(text, default=base_date, fuzzy=True)
                        
                        # Set the timezone to Chicago
                        chicago_tz = pytz.timezone('America/Chicago')
                        local_dt_with_tz = chicago_tz.localize(parsed_dt)
                        
                        # Convert to UTC
                        utc_dt = local_dt_with_tz.astimezone(pytz.UTC)
                        
                        # Format as ISO string
                        summary['appointmentDateTime'] = utc_dt.isoformat()
                        print(f"Converted to UTC using fallback method: {summary['appointmentDateTime']}")
                        
                    except Exception as e2:
                        logger.error(f"Fallback datetime parsing also failed: {str(e2)}")
                        print(f"Fallback datetime parsing also failed: {str(e2)}")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from Gemini response: {str(e)}")
            print(f"Error parsing JSON: {str(e)}")
            print(f"Raw response: {extraction_response.text}")
    except Exception as e:
        logger.error(f"Error calling Gemini API for extraction: {str(e)}")
        print(f"Error with Gemini extraction: {str(e)}")
    
    # Generate a detail summary
    detail_parts = []
    if summary['firstName'] or summary['lastName']:
        name = f"{summary['firstName']} {summary['lastName']}".strip()
        detail_parts.append(f"Customer: {name}")
    if summary['squareFeet']:
        detail_parts.append(f"Property: {summary['squareFeet']} sq ft")
    if summary['bedrooms'] and summary['bathrooms']:
        detail_parts.append(f"{summary['bedrooms']} bed, {summary['bathrooms']} bath")
    if summary['appointmentDateTime']:
        try:
            dt = datetime.fromisoformat(summary['appointmentDateTime'])
            detail_parts.append(f"Appointment: {dt.strftime('%b %d, %Y at %I:%M %p')} UTC")
        except:
            pass
    
    summary['detailSummary'] = ' | '.join(detail_parts)
    print(f"Generated detail summary: {summary['detailSummary']}")
    print("\n===== EXTRACTION COMPLETE =====\n")
    
    return summary


@login_required
def chat_view(request):
    """Render the chat interface"""
    business = get_object_or_404(Business, user=request.user)
    
    # Get all chats for this business
    chats_queryset = Chat.objects.filter(business=business).order_by('-updatedAt')
    
    # Prepare chats with their messages
    chats = {}
    for chat in chats_queryset:
        # Get messages for this chat
        messages = Messages.objects.filter(chat=chat).order_by('createdAt')
        if messages.exists():
            chats[chat.clientPhoneNumber] = list(messages)
    
    context = {
        'business': business,
        'chats': chats,
    }
    
    return render(request, 'ai_agent/chat.html', context)


@csrf_exempt
@login_required
def chat_api(request):
    """
    API endpoint for chat interactions
    """
    if request.method == 'POST':
        try:
            # Parse request data
            data = json.loads(request.body)
            message = data.get('message', '').strip()
            business_id = data.get('business_id', '')
            client_phone_number = data.get('client_phone_number', '')
            
            # Validate required fields
            if not message:
                return JsonResponse({'error': 'Message is required'}, status=400)
            
            # Get or create business
            try:
                business = Business.objects.get(businessId=business_id) if business_id else Business.objects.first()
            except Business.DoesNotExist:
                return JsonResponse({'error': 'Business not found'}, status=404)
            
   
            if client_phone_number:
                # Check if a chat with this phone number already exists for this business
                existing_chat = Chat.objects.filter(
                    clientPhoneNumber=client_phone_number,
                    business=business
                ).first()
                
                if existing_chat:
                    # Use existing chat
                    chat = existing_chat
                    chat_id = str(existing_chat.id)
                else:
                    # Create new chat with phone number
                    chat = Chat.objects.create(
                        clientPhoneNumber=client_phone_number,
                        business=business
                    )
                    chat_id = str(chat.id)
            else:
                return JsonResponse({'error': 'Client phone number is required'}, status=400)
            
            # Save user message
            user_message = Messages(
                chat=chat,
                role='user',
                message=message
            )
            user_message.save()
            
            # Get chat history
            chat_history = Messages.objects.filter(chat=chat).order_by('createdAt')
            
            # Get AI response
            ai_response_text = get_ai_response(chat_history, business.businessId, client_phone_number)
            
            # Save AI response
            ai_message = Messages(
                chat=chat,
                role='assistant',
                message=ai_response_text
            )
            ai_message.save()
            
            # Return response
            return JsonResponse({
                'chat_id': chat_id,
                'response': ai_response_text
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Error in chat API: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
@login_required
def delete_chat(request, client_phone_number):
    """Delete a chat conversation"""
    try:
        business = get_object_or_404(Business, user=request.user)
        
        # Find the chat
        chat = get_object_or_404(Chat, business=business, clientPhoneNumber=client_phone_number)
        
        # Delete the chat (this will cascade delete all related messages)
        chat.delete()
        
        return JsonResponse({'success': True}, safe=False)
    except Exception as e:
        logger.error(f"Error deleting chat: {str(e)}")
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)
