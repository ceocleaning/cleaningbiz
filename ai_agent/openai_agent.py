from dotenv import load_dotenv
import os
import json
from datetime import datetime, timedelta
import pytz
import traceback
from openai import OpenAI

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404

from accounts.models import Business
from bookings.models import Booking
from .models import Chat, Messages, AgentConfiguration
from .api_views import check_availability, book_appointment, get_current_time_in_chicago, calculate_total
from .utils import convert_date_str_to_date
import re

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Define available tools
tools = {
    'check_availability': check_availability,
    'bookAppointment': book_appointment,
    'current_time': get_current_time_in_chicago,
    'calculateTotal': calculate_total
}

# Define OpenAI tools schema
openai_tools = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check if a specific date and time is available for booking",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "The date and time to check availability for (e.g., 'Tomorrow at 2 PM', 'March 15, 2025 at 10 AM')"
                    }
                },
                "required": ["date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bookAppointment",
            "description": "Book an appointment after collecting all required customer information",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "current_time",
            "description": "Get the current time in Chicago timezone",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculateTotal",
            "description": "Calculate the total cost of the appointment",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

class OpenAIAgent:
    """Class to handle OpenAI agent functionality with improved organization and error handling"""
    
    @staticmethod
    def get_dynamic_system_prompt(business_id):
        """Generate a dynamic system prompt based on the business and agent configuration
        stored in the database. Falls back to default prompt if no configuration exists.
        
        Args:
            business_id: The ID of the business to generate the prompt for
            
        Returns:
            String containing the system prompt, or 0 if no configuration exists
        """
        try:
            # Get the business object
            business = Business.objects.get(businessId=business_id)
            
            # Try to get agent configuration for this business
            try:
                agent_config = AgentConfiguration.objects.get(business=business)
                
                system_prompt = f"""You are Sarah, virtual customer support and sales representative for {business.businessName}. You are speaking with a potential customer.

                    ##PRIMARY ROLE AND KNOWLEDGE SOURCE
                    Your primary role is to answer questions about cleaning services using ONLY the information provided by the business. DO NOT make up information or use general knowledge about cleaning that hasn't been explicitly provided by {business.businessName}.

                    ##Prompt
                    {agent_config.prompt or ''}
                    
                    ##CRITICAL TOOL USAGE INSTRUCTIONS:
                    You have access to the following tools to help with the booking process. YOU MUST USE THESE TOOLS when appropriate:

                    1. check_availability: ALWAYS USE THIS TOOL whenever a customer asks about availability or scheduling for a specific date/time
                       - Input: A date and time string (e.g., "Tomorrow at 2 PM", "March 15, 2025 at 10 AM")
                       - When to use: IMMEDIATELY when a customer mentions ANY specific date or time for booking
                       - Example trigger phrases: "Is next Monday available?", "Can I book for tomorrow?", "Do you have availability on Friday?"

                    2. bookAppointment: Use this tool to book an appointment after collecting all required customer information
                       - When to use: After confirming availability and collecting all required customer information

                    3. current_time: Use this tool to get the current time in Chicago timezone
                       - When to use: When a customer asks about current time, business hours, or what time it is
                       - Example trigger phrases: "What time is it?", "What is the current time?", "What time is it now?"

                    4. calculateTotal: Use this tool to calculate the total cost of the appointment
                       - When to use: Before booking an appointment and after confirming all customer details

                    """
                
                return system_prompt
                
            except AgentConfiguration.DoesNotExist:
                # No configuration exists, return 0 to indicate this
                return 0
                
        except Business.DoesNotExist:
            # Business doesn't exist, return 0 to indicate this
            return 0
        except Exception as e:
            print(f"Error generating dynamic system prompt: {str(e)}")
            print(traceback.format_exc())
            return 0
    
    @staticmethod
    def get_or_create_chat(business_id, client_phone_number):
        """Get or create a chat session for a client
        
        Args:
            business_id: The ID of the business
            client_phone_number: The phone number of the client
            
        Returns:
            Chat object or None if error
        """
        try:
            # Get the business object
            business = Business.objects.get(businessId=business_id)
            
            # Try to get an existing chat
            try:
                chat = Chat.objects.get(clientPhoneNumber=client_phone_number)
                return chat
            except Chat.DoesNotExist:
                # Create a new chat
                chat = Chat.objects.create(
                    business=business,
                    clientPhoneNumber=client_phone_number,
                )
                return chat
                
        except Business.DoesNotExist:
            print(f"[DEBUG] Business not found with ID: {business_id}")
            return None
        except Exception as e:
            print(f"[DEBUG] Error getting or creating chat: {str(e)}")
            traceback.print_exc()
            return None
    
    @staticmethod
    def get_chat_messages(client_phone_number):
        """Get all messages for a chat session
        
        Args:
            client_phone_number: The phone number of the client
            
        Returns:
            List of message dictionaries or empty list if error
        """
        try:
            # Get the chat object
            chat = Chat.objects.get(clientPhoneNumber=client_phone_number)
            
            # Get all messages for this chat
            messages = Messages.objects.filter(chat=chat).order_by('createdAt')
            
            # Convert to a list of dictionaries
            message_list = []
            for msg in messages:
                message_list.append({
                    'id': msg.id,
                    'role': msg.role,
                    'message': msg.message,
                    'createdAt': msg.createdAt
                })
                
            return message_list
            
        except Chat.DoesNotExist:
            print(f"[DEBUG] Chat not found for phone number: {client_phone_number}")
            return []
        except Exception as e:
            print(f"[DEBUG] Error getting chat messages: {str(e)}")
            traceback.print_exc()
            return []
    
    @staticmethod
    def format_messages_for_openai(messages, system_prompt):
        """Format messages for OpenAI API
        
        Args:
            messages: List of message dictionaries
            system_prompt: System prompt to use
            
        Returns:
            List of message dictionaries formatted for OpenAI API
        """
        try:
            # Create the formatted messages list
            formatted_messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # Add all user and assistant messages
            for msg in messages:
                if msg['role'] in ['user', 'assistant']:
                    formatted_messages.append({
                        "role": msg['role'],
                        "content": msg['message']
                    })
            
            return formatted_messages
            
        except Exception as e:
            print(f"[DEBUG] Error formatting messages for OpenAI: {str(e)}")
            traceback.print_exc()
            return [{"role": "system", "content": system_prompt}]
    
    @staticmethod
    def execute_tool_call(tool_name, tool_args_raw, client_phone_number):
        """Execute a tool call from the OpenAI API
        
        Args:
            tool_name: The name of the tool to execute
            tool_args_raw: The arguments for the tool as a JSON string or dict
            client_phone_number: The phone number of the client for context
            
        Returns:
            String containing the result of the tool execution
        """
        try:
            print(f"\n[DEBUG] Executing tool call: {tool_name}")
            print(f"[DEBUG] Tool args: {tool_args_raw}")
            print(f"[DEBUG] Client phone number: {client_phone_number}")
            
            # Check if the tool exists
            from .api_views import check_availability, book_appointment, get_current_time_in_chicago, calculate_total
            tools = {
                'check_availability': check_availability,
                'bookAppointment': book_appointment,
                'current_time': get_current_time_in_chicago,
                'calculateTotal': calculate_total
            }
            
            if tool_name not in tools:
                return f"Error: Tool '{tool_name}' not found"
            
            # Parse the arguments
            if isinstance(tool_args_raw, str):
                try:
                    tool_args = json.loads(tool_args_raw)
                except json.JSONDecodeError:
                    return "Error: Invalid JSON in tool arguments"
            else:
                tool_args = tool_args_raw
            
            # Special case for current_time which doesn't need any arguments
            if tool_name == 'current_time':
                try:
                    print(f"[DEBUG] Calling current_time tool")
                    result = tools[tool_name]()
                    print(f"[DEBUG] current_time result: {result}")
                    return result  # Return the string directly, no need for JSON serialization
                except Exception as e:
                    print(f"Error executing current_time tool: {str(e)}")
                    print(f"Error details: {traceback.format_exc()}")
                    return f"Error getting current time: {str(e)}"
            
            # For other tools, we need the chat and business context
            try:
                # Get the chat object for this phone number
                if not client_phone_number:
                    return "Error: Missing client phone number"
                
                chat = Chat.objects.get(clientPhoneNumber=client_phone_number)
                business = chat.business
                
                # Execute the appropriate tool based on the tool name and required arguments
                if tool_name == 'check_availability':
                    # Get date parameter
                    date_str = tool_args.get('date')
                    if not date_str:
                        return "Error: Missing date parameter for check_availability"
                    
                    # Execute the tool with required arguments
                    result = tools[tool_name](business, date_str)
                    return json.dumps(result)
                    
                elif tool_name == 'bookAppointment':
                    # Only extract booking data from conversation when bookAppointment is called
                    print(f"[DEBUG] bookAppointment called - extracting conversation summary")
                    
                    # Get messages for this chat
                    messages = OpenAIAgent.get_chat_messages(client_phone_number)
                    
                    # Extract summary from conversation
                    summary = OpenAIAgent.extract_conversation_summary(messages)
                    
                    # Update the chat with the summary
                    chat.summary = json.dumps(summary)
                    chat.save()
                    
                    # Check if we have enough information to create a booking
                    if not summary:
                        return json.dumps({
                            "success": False,
                            "message": "No conversation summary available. Please collect customer information first."
                        })
                    
                    # Execute the tool with required arguments
                    result = tools[tool_name](business, client_phone_number, summary)
                    return json.dumps(result)
                    
                elif tool_name == 'calculateTotal':
                    # Execute the tool with required arguments
                    result = tools[tool_name](business, client_phone_number)
                    return json.dumps(result)
                    
                else:
                    return f"Error: Unsupported tool '{tool_name}'"
                    
            except Chat.DoesNotExist:
                return f"Error: Chat not found for phone number {client_phone_number}"
            except Exception as e:
                print(f"Error executing tool {tool_name if 'tool_name' in locals() else 'unknown'}: {str(e)}")
                print(f"Error details: {traceback.format_exc()}")
                return f"Error executing tool {tool_name if 'tool_name' in locals() else 'unknown'}: {str(e)}"
                
        except Exception as e:
            print(f"\n===== ERROR in execute_tool_call =====")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print(f"Error details: {traceback.format_exc()}")
            print("===== END ERROR =====\n")
            return f"Error executing tool call: {str(e)}"
    
    @staticmethod
    def get_openai_tools():
        """Get the OpenAI tools configuration for function calling
        
        Returns:
            List of tool definitions in the OpenAI format
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "check_availability",
                    "description": "Check if a specific date and time is available for booking a cleaning appointment",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {
                                "type": "string",
                                "description": "The date and time to check for availability in natural language format (e.g., 'tomorrow at 2pm', 'next Monday at 10am')"
                            }
                        },
                        "required": ["date"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "bookAppointment",
                    "description": "Book a cleaning appointment with the collected customer information",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "current_time",
                    "description": "Get the current time in Chicago timezone (Central Time)",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "calculateTotal",
                    "description": "Calculate the total price for a cleaning service based on property details and selected addons",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            }
        ]
    
    @staticmethod
    def process_ai_response(response, client_phone_number):
        """Process the OpenAI response to execute tool calls and return the updated response
        
        Args:
            response: The OpenAI response object or message object
            client_phone_number: The phone number of the client for context
            
        Returns:
            String containing the final response text
        """
        try:
            print("\n[DEBUG] Processing AI response")
            
            # Check if the response is a ChatCompletion or a ChatCompletionMessage
            if hasattr(response, 'choices'):
                message = response.choices[0].message
            else:
                # It's already a message object
                message = response
                
            # Check if the message has tool calls
            has_tool_calls = hasattr(message, 'tool_calls') and message.tool_calls
            print(f"[DEBUG] Has tool calls: {has_tool_calls}")
            
            if not has_tool_calls:
                # No tool calls, just return the message content
                return message.content
            
            # Process tool calls
            all_tool_results = []
            bookAppointment_called = False
            
            for tool_call in message.tool_calls:
                print(f"[DEBUG] Processing tool call: {tool_call.function.name}")
                print(f"[DEBUG] Tool arguments: {tool_call.function.arguments}")
                
                # Check if this is a bookAppointment call
                if tool_call.function.name == 'bookAppointment':
                    bookAppointment_called = True
                
                # Execute the tool call
                tool_result = OpenAIAgent.execute_tool_call(
                    tool_call.function.name, 
                    tool_call.function.arguments, 
                    client_phone_number
                )
                print(f"[DEBUG] Tool result: {tool_result}")
                
                # Store the tool result for later use
                all_tool_results.append({
                    "tool_id": tool_call.id,
                    "tool_name": tool_call.function.name,
                    "tool_args": tool_call.function.arguments,
                    "result": tool_result
                })
            
            # Generate a natural language response using OpenAI
            print(f"[DEBUG] Generating natural language response from tool results")
            
            # Create a new message for the LLM with tool results
            messages = [
                {"role": "system", "content": "You are Sarah, an AI assistant for a cleaning company. Generate a natural, conversational response based on the tool results. DO NOT mention that you're using tools or APIs. Just incorporate the information naturally. DO NOT use phrases like 'the system shows' or 'I checked and found'. Respond as if you naturally know this information. Keep your response friendly, professional, and conversational. IMPORTANT: ALWAYS ANSWER THE USER'S QUESTION DIRECTLY FIRST, then provide additional context or information if needed.\n\nFor the current_time tool, ALWAYS respond with the exact time information and nothing else. For example, if the tool returns '2025-03-14 12:49 PM (Friday) Central Time', your response should be 'It's currently 12:49 PM on Friday, March 14th, Central Time.' DO NOT add any other information about booking or services when responding to time queries."}
            ]
            
            # Add the original user message for context if available - retrieve all messages without limit
            try:
                chat = Chat.objects.get(clientPhoneNumber=client_phone_number)
                messages_qs = Messages.objects.filter(chat=chat).order_by('-createdAt')
                for msg in messages_qs:
                    messages.append({"role": msg.role, "content": msg.message})
            except (Chat.DoesNotExist, Messages.DoesNotExist):
                pass  # No chat or messages found, continue without context
            
            # Add tool results as assistant messages with tool_call_id
            for result in all_tool_results:
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": result["tool_id"],
                        "type": "function",
                        "function": {
                            "name": result["tool_name"],
                            "arguments": result["tool_args"]
                        }
                    }]
                })
                
                # Format the tool result based on the tool type
                tool_content = result["result"]
                
                # Special handling for current_time tool
                if result["tool_name"] == "current_time":
                    # Make sure we pass the raw time string without any processing
                    tool_content = result["result"]
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": result["tool_id"],
                    "content": tool_content
                })

                # Only save tool messages to database if needed for debugging
                try:
                    Messages.objects.create(
                        chat=chat,
                        role="tool",
                        message=tool_content
                    )
                except Exception as e:
                    print(f"[DEBUG] Error saving tool message: {str(e)}")
            
            # Generate the natural response with full tokens for comprehensive processing
            try:
                print(f"[DEBUG] Calling OpenAI to generate natural response")
                client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
                natural_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    temperature=0.5,
                    max_tokens=1024  # Using full token count for comprehensive responses
                )
                
                # Use the natural response as the final response
                final_response = natural_response.choices[0].message.content
                print(f"[DEBUG] Final response: {final_response}")
                return final_response
            except Exception as e:
                print(f"Error generating natural response: {str(e)}")
                print(f"Error details: {traceback.format_exc()}")
                
                # Safe fallback with better error handling
                try:
                    if 'message' in locals():
                        return message.content
                    elif hasattr(response, 'choices'):
                        return response.choices[0].message.content
                    elif hasattr(response, 'content'):
                        return response.content
                    else:
                        return "I'm sorry, I encountered an error processing the response."
                except Exception:
                    return "I'm sorry, I encountered an error processing the response."
            
        except Exception as e:
            print(f"\n===== ERROR in process_ai_response =====")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print(f"Error details: {traceback.format_exc()}")
            print("===== END ERROR =====\n")
            
            # Safe fallback with better error handling
            try:
                if 'message' in locals():
                    return message.content
                elif hasattr(response, 'choices'):
                    return response.choices[0].message.content
                elif hasattr(response, 'content'):
                    return response.content
                else:
                    return "I'm sorry, I encountered an error processing the response."
            except Exception:
                return "I'm sorry, I encountered an error processing the response."

    @staticmethod
    def extract_conversation_summary(chat_history):
        """
        Extract key information from the conversation history for booking purposes using OpenAI LLM.
        
        Args:
            chat_history: List of message dictionaries with 'role' and 'content' keys
            
        Returns:
            Dictionary with extracted customer information
        """
        # Initialize empty summary with default values
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
        
        try:
            print(f"[DEBUG] Starting conversation summary extraction at {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}")
            
            # Filter to only include user and assistant messages - process all messages without limit
            filtered_messages = []
            for msg in chat_history:  # Process all messages
                if msg.get('role') in ['user', 'assistant'] and msg.get('message'):
                    filtered_messages.append({'role': msg.get('role'), 'content': msg.get('message')})
            
            # Skip if conversation is too short
            if len(filtered_messages) < 2:
                print(f"[DEBUG] Conversation too short to extract summary: {len(filtered_messages)} messages")
                return summary
                
            # Join messages into a single text for analysis, but with clear role indicators
            conversation_text = ""
            for msg in filtered_messages:
                role = "Customer" if msg['role'] == 'user' else "Agent"
                conversation_text += f"{role}: {msg['content']}\n"
            
            print(f"[DEBUG] Extracting summary from conversation: {len(conversation_text)} chars, {len(filtered_messages)} messages")
            
            # Create a detailed system prompt for OpenAI to extract comprehensive information
            system_prompt = f"""
            You are an AI assistant for CEO Cleaners, a professional cleaning service. Your task is to extract specific customer booking information from this conversation.
            Analyze the entire conversation history carefully and extract all relevant details.
            
            Respond ONLY with a valid JSON object containing these keys (leave empty if not found):
            - firstName, lastName: Customer's full name
            - email: Customer's email address
            - phoneNumber: Customer's phone number without any spaces or dashes
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
            
            ONLY return a valid JSON object. No explanations or additional text.
            If you cannot determine a value, leave it as an empty string.
            """
            
            # Initialize OpenAI client
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            
            # Call OpenAI API for extraction with full token allocation for comprehensive extraction
            response = client.chat.completions.create(
                model="gpt-4o",  # Using the most capable model for accurate extraction
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": conversation_text}
                ],
                temperature=0.1,  # Low temperature for more deterministic extraction
                max_tokens=1000,  # Using full token allocation for comprehensive extraction
                response_format={"type": "json_object"}
            )
            
            print(f"[DEBUG] Extraction API call completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}")
            
            # Extract the response content
            extracted_info = response.choices[0].message.content
            print(f"[DEBUG] Raw extraction response: {extracted_info[:200]}...")
            
            try:
                # Parse the JSON response
                extracted_data = json.loads(extracted_info)
                
                # Update summary with extracted data
                for key, value in extracted_data.items():
                    if key in summary and value:
                        summary[key] = value
                
                print(f"[DEBUG] Successfully extracted summary with {len([v for v in summary.values() if v])} non-empty fields")
                
            except json.JSONDecodeError as e:
                print(f"[ERROR] Error parsing extracted information: {str(e)}")
                print(f"[ERROR] Raw extraction response: {extracted_info}")
            
        except Exception as e:
            print(f"[ERROR] Error extracting conversation summary: {str(e)}")
            print(traceback.format_exc())
        
        return summary


# Django views for OpenAI chat
@login_required
def chat_view(request):
    """View for the OpenAI chat interface
    
    Args:
        request: Django request object
        
    Returns:
        Rendered template with chat data
    """
    try:
        # Get the business for this user
        business = get_object_or_404(Business, user=request.user)
        
        # Get all chats for this business
        chats = {}
        chat_objects = Chat.objects.filter(business=business)
        
        for chat in chat_objects:
            # Get messages for this chat
            messages = Messages.objects.filter(chat=chat).order_by('-createdAt')
            if messages.exists():
                chats[chat.clientPhoneNumber] = list(messages)
        
        # Render the template
        return render(request, 'ai_agent/openai_chat.html', {
            'business': business,
            'chats': chats
        })
    except Exception as e:
        print(f"Error in chat_view: {str(e)}")
        traceback.print_exc()
        return render(request, 'ai_agent/openai_chat.html', {
            'error': str(e)
        })

@csrf_exempt
def chat_api(request):
    """API endpoint for OpenAI chat
    
    Args:
        request: Django request object
        
    Returns:
        JsonResponse with the AI response or chat messages
    """
    # Handle GET requests for retrieving messages
    if request.method == 'GET':
        try:
            client_phone_number = request.GET.get('client_phone_number')
            action = request.GET.get('action')
            
            if action == 'get_messages' and client_phone_number:
                # Get all messages for this chat
                messages = OpenAIAgent.get_chat_messages(client_phone_number)
                return JsonResponse({
                    'messages': messages
                })
            else:
                return JsonResponse({
                    'error': 'Invalid action or missing phone number'
                }, status=400)
        except Exception as e:
            print(f"Error in chat_api GET: {str(e)}")
            traceback.print_exc()
            return JsonResponse({
                'error': str(e)
            }, status=500)
    
    # Handle POST requests for chat interaction
    try:
        # Parse the request data
        data = json.loads(request.body)
        business_id = data.get('business_id')
        client_phone_number = data.get('client_phone_number')
        message_text = data.get('message')
        
        print(f"\n[DEBUG] Chat API request")
        print(f"[DEBUG] Business ID: {business_id}")
        print(f"[DEBUG] Client phone number: {client_phone_number}")
        print(f"[DEBUG] Message: {message_text}")
        
        # Validate required fields
        if not business_id or not client_phone_number or not message_text:
            return JsonResponse({
                'error': 'Missing required fields'
            }, status=400)
        
        # Get or create the chat
        chat = OpenAIAgent.get_or_create_chat(business_id, client_phone_number)
        if not chat:
            return JsonResponse({
                'error': 'Failed to get or create chat'
            }, status=500)
        
        # Create a new message
        message = Messages.objects.create(
            chat=chat,
            role='user',
            message=message_text
        )
        
        # Get the system prompt
        system_prompt = OpenAIAgent.get_dynamic_system_prompt(business_id)
      
        # Get all messages for this chat
        messages = OpenAIAgent.get_chat_messages(client_phone_number)
        
        # Format messages for OpenAI
        formatted_messages = OpenAIAgent.format_messages_for_openai(messages, system_prompt)
        
        # Call OpenAI API
        try:
            print(f"[DEBUG] Calling OpenAI API")
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=formatted_messages,
                temperature=0.5,
                max_tokens=1024,
                tools=OpenAIAgent.get_openai_tools()
            )
            
            # Process the response
            ai_response = OpenAIAgent.process_ai_response(response, client_phone_number)
            
            # Save the assistant message
            assistant_message = Messages.objects.create(
                chat=chat,
                role='assistant',
                message=ai_response
            )

            formatted_messages.append({
                'role': 'assistant',
                'content': ai_response
            })
            
            # Analyze and update chat summary
            # Make sure formatted_messages is in the correct format
            # Each message should be a dictionary with 'role' and 'content' keys
            messages_for_summary = formatted_messages.copy()
            
            # Add the latest assistant response if it's not already included
            if ai_response and not any(msg.get('role') == 'assistant' and msg.get('content') == ai_response for msg in messages_for_summary):
                messages_for_summary.append({
                    'role': 'assistant',
                    'content': ai_response
                })
            
            # Extract conversation summary
            summary = OpenAIAgent.extract_conversation_summary(messages_for_summary)
            
            # Update chat summary - ensure it's properly handled as JSON
            print(f"[DEBUG] Updating chat summary with: {json.dumps(summary, indent=2)}")
            
            # Make sure we're handling the JSON field correctly
            if not isinstance(summary, dict):
                print(f"[WARNING] Summary is not a dictionary, converting: {type(summary)}")
                try:
                    if isinstance(summary, str):
                        summary = json.loads(summary)
                    else:
                        summary = dict(summary)
                except Exception as e:
                    print(f"[ERROR] Failed to convert summary to dictionary: {str(e)}")
                    summary = {}
            
            # Update the chat object
            chat.summary = summary
            chat.save()
            
            # Verify the save worked
            refreshed_chat = Chat.objects.get(id=chat.id)
            print(f"[DEBUG] Saved chat summary: {json.dumps(refreshed_chat.summary, indent=2) if refreshed_chat.summary else 'None'}")
            
            # Return the response
            return JsonResponse({
                'response': ai_response
            })
            
        except Exception as e:
            print(f"Error calling OpenAI API: {str(e)}")
            traceback.print_exc()
            return JsonResponse({
                'error': f"Error calling OpenAI API: {str(e)}"
            }, status=500)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        print(f"Error in chat_api: {str(e)}")
        traceback.print_exc()
        return JsonResponse({
            'error': str(e)
        }, status=500)

@csrf_exempt
def delete_chat(request, client_phone_number):
    """API endpoint to delete a chat
    
    Args:
        request: Django request object
        client_phone_number: The phone number of the client
        
    Returns:
        JsonResponse with success or error message
    """
    try:
        # Get the chat object
        chat = Chat.objects.get(clientPhoneNumber=client_phone_number)
        
        # Delete all messages for this chat
        Messages.objects.filter(chat=chat).delete()
        
        # Delete the chat
        chat.delete()
        
        return JsonResponse({
            'success': True
        })
    except Chat.DoesNotExist:
        return JsonResponse({
            'error': 'Chat not found'
        }, status=404)
    except Exception as e:
        print(f"Error in delete_chat: {str(e)}")
        traceback.print_exc()
        return JsonResponse({
            'error': str(e)
        }, status=500)