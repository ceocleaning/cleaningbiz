from dotenv import load_dotenv
import os
import json
import uuid
import logging
import re
from datetime import datetime, timedelta
import pytz
import traceback

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404

from accounts.models import Business
from bookings.models import Booking
from .models import Chat, Messages, AgentConfiguration
from .api_views import check_availability, book_appointment, get_current_time_in_chicago
from .utils import convert_date_str_to_date

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
    # Get the business object
    business = Business.objects.get(businessId=business_id)
    
    # Try to get agent configuration for this business
    try:
        config = AgentConfiguration.objects.get(business=business)
    except AgentConfiguration.DoesNotExist:
        print("Agent configuration not found for business")
        return 0
    
    # Start with base prompt
    prompt = f"""You are {config.agent_name}, {config.agent_role} for {business.businessName}. You are speaking with a potential customer.

        Your primary goals are to:
        1. Answer questions about cleaning services
        2. Collect customer details
        3. Book cleaning appointments

        ##Rules:
        - Greet and engage potential customers professionally
        - Confirm interest in cleaning services
        - Gather essential customer details (name, phone number, email, and address)
        - Collect property details (square footage, bedrooms, bathrooms)
        - Provide service options and pricing transparently
        - Offer discounts when necessary
        - Schedule and confirm cleaning appointments
        - Send booking confirmation and invoice links via email or SMS
        - ALWAYS use tools when appropriate - NEVER skip using a tool when it's needed

        ##CRITICAL TOOL USAGE INSTRUCTIONS:
        You have access to the following tools to help with the booking process. YOU MUST USE THESE TOOLS when appropriate:

        1. check_availability: ALWAYS USE THIS TOOL whenever a customer asks about availability or scheduling for a specific date/time
           - Input: A date and time string (e.g., "Tomorrow at 2 PM", "March 15, 2025 at 10 AM")
           - Business Object
           - When to use: IMMEDIATELY when a customer mentions ANY specific date or time for booking
           - Example trigger phrases: "Is next Monday available?", "Can I book for tomorrow?", "Do you have availability on Friday?"

        2. bookAppointment: Use this tool to book an appointment after collecting all required customer information
           - Input: client_phone_number : String
           - Business Object
           - When to use: After confirming availability and collecting all required customer information

        3. current_time: Use this tool to get the current time in Chicago timezone
           - Input: None
           - When to use: When a customer asks about current time or business hours

        ##TOOL CALLING FORMAT:
        When you need to use a tool, use one of the following formats EXACTLY as shown:
        
        Format 1 (preferred):
        <tool>tool_name(parameters)</tool>

        Format 2 (alternative):
        ```tool_code tool_name(parameters) ```

        EXAMPLES OF CORRECT TOOL USAGE:
        <tool>check_availability(Tomorrow at 2 PM, business_obj)</tool>
        <tool>current_time()</tool>
        <tool>bookAppointment(client_phone_number, business_obj)</tool>

        IMPORTANT: DO NOT try to make up responses that should come from tools. When a customer asks about availability, ALWAYS use the check_availability tool.

        Be friendly, professional, and helpful. Follow the conversation flow carefully and wait for user responses before moving to the next step.

        Maintain a conversational tone and allow pauses for natural interaction.

        Always include "AM" or "PM" when mentioning time (e.g., "Three thirty PM").
        Never say "O'Clock." Instead, say "One PM."

        Always verify appointment availability before booking.

        ##Business Information
        {config.business_description}
        
        ##Business Mission
        {config.business_mission}

        ##Services
        {config.services}

        ##Custom Instructions
        {config.custom_instructions}

        ##Script - AI has to follow this script
        {config.script}
        """

    
    return prompt
        
  


def execute_tool_call(tool_call, client_phone_number):
    """Execute a tool call and return the result"""
    try:
        print("\n===== STARTING execute_tool_call =====")
        print(f"Tool call: {tool_call}")
        
        # Extract tool name and arguments
        tool_name = tool_call.get('name')
        tool_args = tool_call.get('args', {})
        
        if not tool_name:
            print("Error: Missing tool name in tool call")
            return "Error: Missing tool name in tool call"
        
        print(f"Tool name: {tool_name}")
        print(f"Tool args: {tool_args}")
        
        # Check if the tool exists
        if tool_name not in tools:
            print(f"Tool not found: {tool_name}")
            return f"Error: Tool '{tool_name}' not found"
        
        # Special case for current_time which doesn't need chat or business context
        if tool_name == 'current_time':
            print("Executing current_time tool")
            try:
                result = tools[tool_name]()
                print(f"Current time result: {result}")
                return result  # Return the string directly, no need for JSON serialization
            except Exception as e:
                print(f"Error executing current_time tool: {str(e)}")
                print(f"Error details: {traceback.format_exc()}")
                return f"Error getting current time: {str(e)}"
        
        # For other tools, we need the chat and business context
        try:
            # Get the chat object for this phone number
            if not client_phone_number:
                print("Error: Missing client phone number")
                return "Error: Missing client phone number"
                
            chat = Chat.objects.get(clientPhoneNumber=client_phone_number)
            print(f"Found chat: {chat.id}")
            
            # Get the business associated with this chat
            business = chat.business
            print(f"Business: {business.businessName}")
            
            # Execute the appropriate tool
            if tool_name == 'check_availability':
                print("Executing check_availability tool")
                # Extract date parameter from tool args
                date_string = tool_args
                if isinstance(tool_args, dict):
                    date_string = tool_args.get('date', '')
                
                if not date_string:
                    print("Error: Missing date parameter for check_availability")
                    return "Error: Missing date parameter for check_availability"
                    
                print(f"Date string: {date_string}")
                try:
                    result = tools[tool_name](business, date_string)
                    print(f"check_availability result: {result}")
                except Exception as e:
                    print(f"Error executing check_availability: {str(e)}")
                    print(f"Error details: {traceback.format_exc()}")
                    return f"Error checking availability: {str(e)}"
                
            elif tool_name == 'bookAppointment':
                print("Executing bookAppointment tool")
                # No need to validate fields here as we're now passing client_phone_number
                # and the validation will happen in the book_appointment function
                
                try:
                    result = tools[tool_name](business, client_phone_number)
                    print(f"bookAppointment result: {result}")
                except Exception as e:
                    print(f"Error executing bookAppointment: {str(e)}")
                    print(f"Error details: {traceback.format_exc()}")
                    return f"Error booking appointment: {str(e)}"
                
            else:
                print(f"Unknown tool execution path: {tool_name}")
                return f"Error: Unknown tool execution path for '{tool_name}'"
            
            print(f"Tool result: {result}")
            print("===== COMPLETED execute_tool_call =====\n")
            return json.dumps(result, default=str)
            
        except Chat.DoesNotExist:
            print(f"\n===== ERROR in execute_tool_call =====")
            print(f"Chat not found for phone number: {client_phone_number}")
            print("===== END ERROR =====\n")
            return "Error: Chat not found"
            
    except Exception as e:
        print(f"\n===== ERROR in execute_tool_call =====")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print(f"Error details: {traceback.format_exc()}")
        print("===== END ERROR =====\n")
        return f"Error executing tool {tool_name if 'tool_name' in locals() else 'unknown'}: {str(e)}"


def process_ai_response(response_text, client_phone_number, formatted_messages=None):
    """
    Process the AI response to execute tool calls and return the updated response
    """
    try:
        print("\n===== STARTING process_ai_response =====")
        print(f"Response text length: {len(response_text)}")
        
        # Check if the response contains tool calls
        has_tool_tag = "<tool>" in response_text and "</tool>" in response_text
        has_tool_code = "```tool_code" in response_text
        
        print(f"Has tool tag format: {has_tool_tag}")
        print(f"Has tool_code format: {has_tool_code}")
        
        # Track all tool results to generate a final response
        all_tool_results = []
        original_response = response_text
        
        # Process tool calls in <tool>tool_name(parameters)</tool> format
        if has_tool_tag:
            print("Processing tool tag format calls")
            
            # Extract tool call using regex
            tool_pattern = r"<tool>([^(]+)\(([^)]*)\)</tool>"
            tool_matches = re.findall(tool_pattern, response_text, re.DOTALL)
            
            print(f"Number of tool tag matches found: {len(tool_matches)}")
            
            # Process each tool call
            for tool_name, tool_args_str in tool_matches:
                print(f"Processing tool: {tool_name}")
                print(f"Tool args string: {tool_args_str}")
                
                try:
                    # Clean up tool name and args
                    tool_name = tool_name.strip()
                    tool_args_str = tool_args_str.strip()
                    tool_args = {}
                    
                    # Handle different tools
                    if tool_name == 'current_time':
                        # No arguments needed for current_time
                        pass
                    elif tool_name == 'check_availability':
                        # For check_availability, use the string directly as the date parameter
                        if tool_args_str:
                            # If it's a direct string parameter
                            tool_args = tool_args_str
                    elif tool_name == 'bookAppointment':
                        # For bookAppointment, we now just pass the client_phone_number directly
                        # No need to parse any arguments as the phone number is already available
                        tool_args = client_phone_number
                    elif tool_name == 'current_time':
                        # No arguments needed for current_time
                        pass
                    
                    print(f"Parsed tool args: {tool_args}")
                    
                    # Create a tool call object
                    tool_call = {
                        "name": tool_name,
                        "args": tool_args
                    }
                    
                    # Execute the tool call
                    print(f"Executing tool call: {tool_call['name']}")
                    tool_result = execute_tool_call(tool_call, client_phone_number)
                    print(f"Tool execution result: {tool_result}")
                    
                    # Store the tool result for later processing
                    all_tool_results.append({
                        "tool_name": tool_name,
                        "tool_args": tool_args_str,
                        "result": tool_result
                    })
                    
                    # Replace the tool call in the response with a placeholder
                    tool_call_text = f"<tool>{tool_name}({tool_args_str})</tool>"
                    response_text = response_text.replace(tool_call_text, f"[TOOL_RESULT_{len(all_tool_results)-1}]")
                    
                except Exception as e:
                    print(f"Error executing tool {tool_name}: {str(e)}")
                    print(f"Error details: {traceback.format_exc()}")
                    error_msg = f"Error executing tool {tool_name}: {str(e)}"
                    tool_call_text = f"<tool>{tool_name}({tool_args_str})</tool>"
                    response_text = response_text.replace(tool_call_text, 
                                                      f"\n\nTool Error: {error_msg}\n\n")
        
        # Process tool calls in ```tool_code tool_name(parameters) ``` format
        if has_tool_code:
            print("Processing tool_code format calls")
            
            # Extract tool call using regex
            code_pattern = r"```tool_code\s+([^(]+)\(([^)]*)\)\s*```"
            code_matches = re.findall(code_pattern, response_text, re.DOTALL)
            
            print(f"Number of tool_code matches found: {len(code_matches)}")
            
            # Process each tool call
            for tool_name, tool_args_str in code_matches:
                print(f"Processing tool_code: {tool_name}")
                print(f"Tool_code args string: {tool_args_str}")
                
                try:
                    # Clean up tool name and args
                    tool_name = tool_name.strip()
                    tool_args_str = tool_args_str.strip()
                    tool_args = {}
                    
                    # Handle different tools
                    if tool_name == 'current_time':
                        # No arguments needed for current_time
                        pass
                    elif tool_name == 'check_availability':
                        # For check_availability, use the string directly as the date parameter
                        if tool_args_str:
                            # If it's a direct string parameter
                            tool_args = tool_args_str
                    elif tool_name == 'bookAppointment':
                        # For bookAppointment, we now just pass the client_phone_number directly
                        # No need to parse any arguments as the phone number is already available
                        tool_args = client_phone_number
                    elif tool_name == 'current_time':
                        # No arguments needed for current_time
                        pass
                    
                    print(f"Parsed tool_code args: {tool_args}")
                    
                    # Create a tool call object
                    tool_call = {
                        "name": tool_name,
                        "args": tool_args
                    }
                    
                    # Execute the tool call
                    print(f"Executing tool_code call: {tool_call['name']}")
                    tool_result = execute_tool_call(tool_call, client_phone_number)
                    print(f"Tool_code execution result: {tool_result}")
                    
                    # Store the tool result for later processing
                    all_tool_results.append({
                        "tool_name": tool_name,
                        "tool_args": tool_args_str,
                        "result": tool_result
                    })
                    
                    # Replace the tool call in the response with a placeholder
                    tool_call_text = f"```tool_code {tool_name}({tool_args_str}) ```"
                    response_text = response_text.replace(tool_call_text, f"[TOOL_RESULT_{len(all_tool_results)-1}]")
                    
                except Exception as e:
                    print(f"Error executing tool_code {tool_name}: {str(e)}")
                    print(f"Error details: {traceback.format_exc()}")
                    error_msg = f"Error executing tool {tool_name}: {str(e)}"
                    tool_call_text = f"```tool_code {tool_name}({tool_args_str}) ```"
                    response_text = response_text.replace(tool_call_text, 
                                                      f"\n\nTool Error: {error_msg}\n\n")
        
        # If we have tool results, generate a natural language response using LLM
        if all_tool_results and formatted_messages:
            print(f"Generating natural language response for {len(all_tool_results)} tool results")
            
            # Create a new prompt for the LLM to generate a natural response
            tool_results_text = ""
            for idx, result in enumerate(all_tool_results):
                tool_name = result["tool_name"]
                tool_args = result["tool_args"]
                tool_result = result["result"]
                
                # Format the tool result based on the tool type
                if tool_name == "check_availability":
                    try:
                        # Parse the JSON result
                        if isinstance(tool_result, str):
                            result_data = json.loads(tool_result)
                        else:
                            result_data = tool_result
                            
                        # Extract availability information
                        is_available = result_data.get("available", False)
                        parsed_datetime = result_data.get("parsed_datetime", "")
                        cleaners = result_data.get("cleaners", [])
                        
                        if is_available:
                            cleaner_names = ", ".join([c.get("name", "Unknown") for c in cleaners])
                            tool_results_text += f"Tool: {tool_name}\nArgs: {tool_args}\nResult: Available on {parsed_datetime}. Available cleaners: {cleaner_names}\n\n"
                        else:
                            alternative_slots = result_data.get("alternative_slots", [])
                            alternatives_text = ", ".join(alternative_slots) if alternative_slots else "No alternative slots available"
                            tool_results_text += f"Tool: {tool_name}\nArgs: {tool_args}\nResult: Not available on {parsed_datetime}. Alternative slots: {alternatives_text}\n\n"
                    except Exception as e:
                        print(f"Error formatting check_availability result: {str(e)}")
                        tool_results_text += f"Tool: {tool_name}\nArgs: {tool_args}\nResult: {tool_result}\n\n"
                elif tool_name == "current_time":
                    tool_results_text += f"Tool: {tool_name}\nResult: {tool_result}\n\n"
                elif tool_name == "bookAppointment":
                    try:
                        # Parse the JSON result
                        if isinstance(tool_result, str):
                            result_data = json.loads(tool_result)
                        else:
                            result_data = tool_result
                            
                        # Extract booking information
                        success = result_data.get("success", False)
                        booking_id = result_data.get("booking_id", "")
                        message = result_data.get("message", "")
                        
                        if success:
                            tool_results_text += f"Tool: {tool_name}\nArgs: {tool_args}\nResult: Booking successful. Booking ID: {booking_id}. {message}\n\n"
                        else:
                            tool_results_text += f"Tool: {tool_name}\nArgs: {tool_args}\nResult: Booking failed. {message}\n\n"
                    except Exception as e:
                        print(f"Error formatting bookAppointment result: {str(e)}")
                        tool_results_text += f"Tool: {tool_name}\nArgs: {tool_args}\nResult: {tool_result}\n\n"
                else:
                    # Generic formatting for other tools
                    tool_results_text += f"Tool: {tool_name}\nArgs: {tool_args}\nResult: {tool_result}\n\n"
            
            # Create a new system prompt for generating natural response
            natural_response_prompt = """You are an AI assistant for a cleaning company. 
            You need to generate a natural, conversational response based on the original message and tool results.
            
            DO NOT mention that you're using tools or APIs. Just incorporate the information naturally.
            DO NOT use phrases like 'the system shows' or 'I checked and found'.
            DO NOT include any tool call syntax in your response.
            
            Respond as if you naturally know this information.
            Keep your response friendly, professional, and conversational."""
            
            # Create a new message for the LLM
            natural_response_messages = [
                {"role": "model", "parts": [{"text": natural_response_prompt}]},
                {"role": "user", "parts": [{"text": f"Original AI response:\n{original_response}\n\nTool Results:\n{tool_results_text}\n\nGenerate a natural, conversational response that incorporates the tool results:"}]}
            ]
            
            # Generate the natural response
            print("Calling model.generate_content for natural response...")
            try:
                natural_response = model.generate_content(
                    natural_response_messages,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.7,
                        max_output_tokens=1024,
                        top_p=0.95,
                        top_k=40,
                    )
                )
                
                # Use the natural response as the final response
                final_response = natural_response.text
                print(f"Generated natural response: {final_response}")
                return final_response
            except Exception as e:
                print(f"Error generating natural response: {str(e)}")
                # Fall back to the original response with placeholders replaced
                
                # Replace placeholders with actual tool results
                for idx, result in enumerate(all_tool_results):
                    placeholder = f"[TOOL_RESULT_{idx}]"
                    result_str = json.dumps(result["result"]) if isinstance(result["result"], dict) else str(result["result"])
                    response_text = response_text.replace(placeholder, f"\n\nTool Result: {result_str}\n\n")
                
                return response_text
        elif all_tool_results:
            # If we have tool results but no formatted_messages, replace placeholders with actual results
            for idx, result in enumerate(all_tool_results):
                placeholder = f"[TOOL_RESULT_{idx}]"
                result_str = json.dumps(result["result"]) if isinstance(result["result"], dict) else str(result["result"])
                response_text = response_text.replace(placeholder, f"\n\nTool Result: {result_str}\n\n")
        
        print(f"Has tool tag format: {has_tool_tag}")
        print(f"Has tool_code format: {has_tool_code}")
        print("===== COMPLETED process_ai_response =====\n")
        return response_text
        
    except Exception as e:
        print(f"\n===== ERROR in process_ai_response =====")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print(f"Error details: {traceback.format_exc()}")
        print("===== END ERROR =====\n")
        return response_text


def get_ai_response(messages, business_id, client_phone_number):
    """
    Get response from Google Gemini AI with tool calling capabilities
    """
    try:
        print("\n===== STARTING get_ai_response =====")
        print(f"Business ID: {business_id}")
        print(f"Client Phone: {client_phone_number}")
        print(f"Number of messages: {len(messages)}")
        
        # Get the system prompt (now dynamic based on business configuration)
        system_prompt = get_dynamic_system_prompt(business_id)
        print(f"System prompt length: {len(system_prompt)}")
        
        # Format messages for the model
        formatted_messages = []
        
        # Add system prompt as the first message
        formatted_messages.append({"role": "model", "parts": [{"text": system_prompt}]})
        
        # Add user and model messages
        for msg in messages:
            role = "user" if msg.role == "user" else "model"
            formatted_messages.append({"role": role, "parts": [{"text": msg.message}]})
        
        print(f"Total formatted messages: {len(formatted_messages)}")
        print("Preparing to call Gemini API...")
        
        # Generate response from the model
        print("Calling model.generate_content...")
        response = model.generate_content(
            formatted_messages,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=1024,
                top_p=0.95,
                top_k=40,
            )
        )
        print("Gemini API call completed successfully")
        
        # Process the response to execute any tool calls
        print("Processing AI response...")
        processed_response = process_ai_response(response.text, client_phone_number, formatted_messages)
        
        print("===== COMPLETED get_ai_response =====\n")
        return processed_response
        
    except Exception as e:
        print(f"\n===== ERROR in get_ai_response =====")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print(f"Error details: {traceback.format_exc()}")
        print("===== END ERROR =====\n")
        return f"I'm sorry, I encountered an error: {str(e)}"


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
        'address1': '',
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
        - address1: Street address (just the street part, no city/state/zip)
        - city: City name
        - state: State
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
        - summary: This is the summary of the conversation
        
        Use empty strings for any information that is not present in the conversation.
        
        IMPORTANT: DO NOT try to make up responses that should come from tools. When a customer asks about availability, ALWAYS use the check_availability tool.

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
               
            
            # Convert appointment date and time to UTC if present
            if summary['appointmentDateTime']:
                try:
                    local_datetime_str = summary['appointmentDateTime']
                    print(f"Extracted appointment text: {local_datetime_str}")
                    
                    # Use convert_date_str_to_date function
                    summary['appointmentDateTime'] = convert_date_str_to_date(local_datetime_str)
                    print(f"Converted appointment to UTC: {summary['appointmentDateTime']}")
                    
                except Exception as e:
                    print(f"Error converting datetime: {str(e)}")
                    print(f"Will try fallback datetime parsing methods")
                    
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {str(e)}")
            print(f"Raw response: {extraction_response.text}")
    except Exception as e:
        print(f"Error calling Gemini API for extraction: {str(e)}")
        print(f"Error with Gemini extraction: {str(e)}")
    
   
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

    print("\n===== CHAT API REQUEST =====")
    if request.method == 'POST':
        try:
            print("Processing POST request")
            # Parse request data
            data = json.loads(request.body)
            message = data.get('message', '').strip()
            business_id = data.get('business_id', '')
            client_phone_number = data.get('client_phone_number', '')
            
            print(f"Message: {message[:50]}..." if len(message) > 50 else f"Message: {message}")
            print(f"Business ID: {business_id}")
            print(f"Client phone: {client_phone_number}")
            
            # Validate required fields
            if not message:
                print("Error: Message is required")
                return JsonResponse({'error': 'Message is required'}, status=400)
            
            # Get or create business
            try:
                business = Business.objects.get(businessId=business_id) if business_id else Business.objects.first()
                print(f"Business found: {business.businessName}")
            except Business.DoesNotExist:
                print("Error: Business not found")
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
                    client_phone_number = str(existing_chat.clientPhoneNumber)
                    print(f"Using existing chat: {chat.id}")
                else:
                    # Create new chat with phone number
                    chat = Chat.objects.create(
                        clientPhoneNumber=client_phone_number,
                        business=business
                    )
                    client_phone_number = str(chat.clientPhoneNumber)
                    print(f"Created new chat: {chat.id}")
            else:
                print("Error: Client phone number is required")
                return JsonResponse({'error': 'Client phone number is required'}, status=400)
            
            # Save user message
            user_message = Messages(
                chat=chat,
                role='user',
                message=message
            )
            user_message.save()
            print("User message saved")
            
            # Get chat history
            chat_history = Messages.objects.filter(chat=chat).order_by('createdAt')
            print(f"Retrieved {chat_history.count()} messages from chat history")
            
            # Get AI response
            print("Calling get_ai_response...")
            ai_response_text = get_ai_response(chat_history, business.businessId, client_phone_number)
            print("AI response received")
            print(f"AI response length: {len(ai_response_text)}")
            
            # Save AI response
            ai_message = Messages(
                chat=chat,
                role='assistant',
                message=ai_response_text
            )
            ai_message.save()
            print("AI message saved")

            # Update conversation summary after AI response
            chat_history = Messages.objects.filter(chat=chat).order_by('createdAt')
            summary = extract_conversation_summary(chat_history)
            chat.summary = summary
            chat.save()
            print("Chat summary updated after AI response")
            
            # Return response
            print("Returning JSON response")
            return JsonResponse({
                'client_phone_number': client_phone_number,
                'response': ai_response_text
            })
            
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON - {str(e)}")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            print(f"\n===== ERROR in chat_api =====")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print(f"Error details: {traceback.format_exc()}")
            print("===== END ERROR =====\n")
            return JsonResponse({'error': str(e)}, status=500)
    else:
        print(f"Method not allowed: {request.method}")
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
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)
