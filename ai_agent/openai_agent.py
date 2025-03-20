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
    def get_or_create_chat(business_id, client_phone_number, session_key):
        """Get or create a chat session for a client
        
        Args:
            business_id: The ID of the business
            client_phone_number: The phone number of the client
            session_key: The session key of the client
        Returns:
            Chat object or None if error
        """
        try:
            # Get the business object
            business = Business.objects.get(businessId=business_id)
            
            # Try to get an existing chat
            try:
                if client_phone_number:
                    chat = Chat.objects.get(clientPhoneNumber=client_phone_number)
                else:
                    chat = Chat.objects.get(sessionKey=session_key)
                return chat
            except Chat.DoesNotExist:
                # Create a new chat
                if client_phone_number:
                    chat = Chat.objects.create(
                        business=business,
                        clientPhoneNumber=client_phone_number,
                    )
                else:
                    chat = Chat.objects.create(
                        business=business,
                        sessionKey=session_key,
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
    def get_chat_messages(client_phone_number, session_key):
        """Get all messages for a chat session
        
        Args:
            client_phone_number: The phone number of the client
            session_key: The session key of the client
        Returns:
            List of message dictionaries or empty list if error
        """
        try:
            # Get the chat object
            if client_phone_number:
                chat = Chat.objects.get(clientPhoneNumber=client_phone_number)
            else:
                chat = Chat.objects.get(sessionKey=session_key)
            
            # Get all messages for this chat
            messages = Messages.objects.filter(chat=chat).order_by('createdAt')
            
            # Convert to a list of dictionaries
            message_list = []
            for msg in messages:
                # Use 'content' key for consistency with OpenAI format
                message_list.append({
                    'id': msg.id,
                    'role': msg.role,
                    'content': msg.message,  # Use content key for OpenAI compatibility
                    'message': msg.message,   # Keep message key for backward compatibility
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
                    # Check if the message has 'content' or 'message' key
                    content = msg.get('content') or msg.get('message')
                    if content:  # Only add if there's content
                        formatted_messages.append({
                            "role": msg['role'],
                            "content": content
                        })
            
            return formatted_messages
            
        except Exception as e:
            print(f"[DEBUG] Error formatting messages for OpenAI: {str(e)}")
            traceback.print_exc()
            return [{"role": "system", "content": system_prompt}]
    
    @staticmethod
    def execute_tool_call(tool_name, tool_args_raw, client_phone_number, business):
        """Execute a tool call from the OpenAI API
        
        Args:
            tool_name: The name of the tool to execute
            tool_args_raw: The arguments for the tool as a JSON string or dict
            client_phone_number: The phone number of the client for context
            business: The business object
            
        Returns:
            String containing the result of the tool execution
        """
        try:
            print(f"\n[DEBUG] Executing tool call: {tool_name}")
            print(f"[DEBUG] Tool arguments: {tool_args_raw}")
            
            # Parse tool arguments if they're a string
            if isinstance(tool_args_raw, str):
                try:
                    tool_args = json.loads(tool_args_raw)
                except json.JSONDecodeError as e:
                    print(f"[ERROR] Error parsing tool arguments: {str(e)}")
                    return json.dumps({
                        "error": f"Error parsing tool arguments: {str(e)}"
                    })
            else:
                tool_args = tool_args_raw
            
            # Get available tools
            from .api_views import check_availability, calculate_total, book_appointment
            
            tools = {
                'check_availability': check_availability,
                'calculateTotal': calculate_total,
                'bookAppointment': book_appointment
            }
            
            # Check if the tool exists
            if tool_name not in tools:
                print(f"[ERROR] Unknown tool: {tool_name}")
                return json.dumps({
                    "error": f"Unknown tool: {tool_name}"
                })
                
            # Check if we have a client phone number
            if not client_phone_number:
                print(f"[ERROR] Missing client phone number")
                return json.dumps({
                    "error": "Missing client phone number"
                })
            
            # Execute the appropriate tool based on the tool name and required arguments
            if tool_name == 'check_availability':
                # Extract date from arguments
                date = tool_args.get('date')
                if not date:
                    return json.dumps({
                        "error": "Missing required argument: date"
                    })
                
                # Execute the tool with required arguments
                result = tools[tool_name](business, date)
                return json.dumps(result)
                
            elif tool_name == 'calculateTotal':
                # Get messages for this chat
                messages = OpenAIAgent.get_chat_messages(client_phone_number)
                
                # Format messages for the summary extraction
                formatted_messages = []
                for msg in messages:
                    if isinstance(msg, dict) and 'role' in msg:
                        # Handle different message formats
                        content = msg.get('content') or msg.get('message')
                        if content:
                            formatted_messages.append({
                                'role': msg['role'],
                                'content': content
                            })
                
                # Extract conversation summary
                if formatted_messages:
                    try:
                        # Extract conversation summary
                        summary = OpenAIAgent.extract_conversation_summary(formatted_messages)
                        
                        # Update chat summary in database
                        chat = Chat.objects.get(clientPhoneNumber=client_phone_number)
                        if isinstance(summary, dict):
                            chat.summary = summary
                            chat.save()
                            print(f"[DEBUG] Successfully saved summary to chat in calculateTotal: {len(summary.keys())} fields")
                        else:
                            print(f"[DEBUG] Summary is not a dict, cannot save in calculateTotal: {type(summary)}")
                    except Exception as e:
                        print(f"[DEBUG] Error extracting conversation summary in calculateTotal: {str(e)}")
                        traceback.print_exc()
                
                # Execute the tool with required arguments
                result = tools[tool_name](business, client_phone_number)
                return json.dumps(result)
                
            elif tool_name == 'bookAppointment':
                # Get messages for this chat
                messages = OpenAIAgent.get_chat_messages(client_phone_number)
                
                # Format messages for the summary extraction
                formatted_messages = []
                for msg in messages:
                    if isinstance(msg, dict) and 'role' in msg:
                        # Handle different message formats
                        content = msg.get('content') or msg.get('message')
                        if content:
                            formatted_messages.append({
                                'role': msg['role'],
                                'content': content
                            })
                
                # Extract summary from conversation
                try:
                    chat = Chat.objects.get(clientPhoneNumber=client_phone_number)
                    summary = OpenAIAgent.extract_conversation_summary(formatted_messages)
                    
                    # Update the chat with the summary
                    if isinstance(summary, dict):
                        chat.summary = summary
                        chat.save()
                        print(f"[DEBUG] Successfully saved summary to chat in bookAppointment: {len(summary.keys())} fields")
                    else:
                        print(f"[DEBUG] Summary is not a dict, cannot save in bookAppointment: {type(summary)}")
                        return json.dumps({
                            "success": False,
                            "message": "Error processing conversation summary. Please try again."
                        })
                except Exception as e:
                    print(f"[DEBUG] Error extracting conversation summary in bookAppointment: {str(e)}")
                    traceback.print_exc()
                    return json.dumps({
                        "success": False,
                        "message": "Error processing conversation summary. Please try again."
                    })
                
                # Check if we have enough information to create a booking
                if not summary or not isinstance(summary, dict) or len([v for v in summary.values() if v]) < 5:
                    return json.dumps({
                        "success": False,
                        "message": "Not enough customer information available. Please collect more details first."
                    })
                
                # Execute the tool with required arguments
                result = tools[tool_name](business, client_phone_number)
                return json.dumps(result)
                
            else:
                return json.dumps({
                    "error": f"Unknown tool: {tool_name}"
                })
                
        except Exception as e:
            print(f"[ERROR] Error executing tool call: {str(e)}")
            traceback.print_exc()
            return json.dumps({
                "error": f"Error executing tool call: {str(e)}"
            })
    
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
    def process_ai_response(response, client_phone_number, business):
        """Process the AI response from OpenAI API
        
        Args:
            response: The response from OpenAI API
            client_phone_number: The phone number of the client
            business: The business object
            
        Returns:
            Dictionary with response content and any tool call results
        """
        try:
            # Extract the response content
            content = response.choices[0].message.content or ""
            
            # Check if there are any tool calls
            tool_calls = response.choices[0].message.tool_calls
            
            if tool_calls:
                print(f"[DEBUG] Found {len(tool_calls)} tool calls in response")
                
                # Process each tool call
                tool_call_results = []
                for tool_call in tool_calls:
                    try:
                        # Execute the tool call
                        result = OpenAIAgent.execute_tool_call(
                            tool_call.function.name,
                            tool_call.function.arguments,
                            client_phone_number,
                            business
                        )
                        
                        # Add to results
                        tool_call_results.append({
                            'tool_call_id': tool_call.id,
                            'result': result
                        })
                    except Exception as e:
                        print(f"[ERROR] Error executing tool call: {str(e)}")
                        traceback.print_exc()
                        tool_call_results.append({
                            'tool_call_id': tool_call.id,
                            'result': json.dumps({
                                "error": f"Error executing tool call: {str(e)}"
                            })
                        })
                
                # Now we need to generate a follow-up response based on the tool results
                # First, prepare the messages for the follow-up call
                messages = []
                
                # Add a more detailed system prompt that ensures continuity with the business script
                system_prompt = f"""You are Sarah, an SMS agent for {business.businessName}, a professional cleaning company. 
                                    
                    You MUST follow these instructions when responding after tool calls:
                    1. Generate a natural, conversational response based on the tool results
                    2. NEVER mention that you're using tools, APIs, or checking systems
                    3. Speak as if you naturally know this information
                    4. Maintain the conversation flow from before the tool call - continue where you left off
                    5. Follow up with the next logical step in the conversation based on your script
                    6. If you were collecting information before the tool call, continue collecting any missing information
                    7. If the tool provided availability or pricing, confirm it and ask if the customer wants to proceed with booking
                    8. If the tool completed a booking, Ask client to pay by clicking on the link received through sms and email and ask if there's anything else they need
                    9. Keep your tone friendly, professional, and conversational
                    10. Remember your role is to guide the customer through the entire booking process

                    Your primary goal is to collect all necessary information and complete the booking process efficiently.
                """
                messages.append({"role": "system", "content": system_prompt})
                
                chat = Chat.objects.get(clientPhoneNumber=client_phone_number)
                # Add context about the current conversation state to help the AI continue properly
                if chat and hasattr(chat, 'summary') and chat.summary:
                    # Extract relevant context from the chat summary
                    context_prompt = "Current conversation context:\n"
                    
                    # Add collected customer information
                    customer_info = []
                    for field in ['firstName', 'lastName', 'email', 'phoneNumber', 'address']:
                        if chat.summary.get(field):
                            customer_info.append(f"- {field}: {chat.summary.get(field)}")
                    
                    if customer_info:
                        context_prompt += "\nCustomer information collected:\n" + "\n".join(customer_info) + "\n"
                    
                    # Add property details if available
                    property_info = []
                    for field in ['bedrooms', 'bathrooms', 'squareFeet', 'serviceType']:
                        if chat.summary.get(field):
                            property_info.append(f"- {field}: {chat.summary.get(field)}")
                    
                    if property_info:
                        context_prompt += "\nProperty details collected:\n" + "\n".join(property_info) + "\n"
                    
                    # Add conversation stage information
                    if chat.summary.get('conversationStage'):
                        context_prompt += f"\nCurrent conversation stage: {chat.summary.get('conversationStage')}\n"
                        
                    # Add this context to the messages
                    messages.append({"role": "system", "content": context_prompt})
                
                # Add the original assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [{
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in tool_calls]
                })
                
                # Add the tool results
                for result in tool_call_results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": result["tool_call_id"],
                        "content": result["result"]
                    })
                
                try:
                    # Call OpenAI again to generate a response based on the tool results
                    print(f"[DEBUG] Calling OpenAI to generate response based on tool results")
                    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                    follow_up_response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=messages,
                        temperature=0.5,
                        max_tokens=1000
                    )
                    
                    # Extract the follow-up response content
                    follow_up_content = follow_up_response.choices[0].message.content or ""
                    print(f"[DEBUG] Follow-up response: {follow_up_content[:100]}...")
                    
                    # Return both the original content, tool results, and follow-up content
                    return {
                        'content': follow_up_content,  # Use the follow-up content as the main response
                        'original_content': content,   # Keep the original content for reference
                        'tool_call_results': tool_call_results
                    }
                except Exception as e:
                    print(f"[ERROR] Error generating follow-up response: {str(e)}")
                    traceback.print_exc()
                    # Fall back to returning the original content and tool results
                    return {
                        'content': "I'm sorry, I encountered an error processing your request. Please try again.",
                        'original_content': content,
                        'tool_call_results': tool_call_results,
                        'error': str(e)
                    }
                
            else:
                # No tool calls, just return the content
                return {
                    'content': content
                }
                
        except Exception as e:
            print(f"[ERROR] Error processing AI response: {str(e)}")
            traceback.print_exc()
            return {
                'content': "I'm sorry, I encountered an error processing your request. Please try again.",
                'error': str(e)
            }
    
    @staticmethod
    def extract_conversation_summary(chat_history):
        """
        Extract key information from the conversation history for booking purposes using OpenAI LLM.
        
        Args:
            chat_history: List of message dictionaries with 'role' and 'content' or 'message' keys
            
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
                # Handle different message formats
                if isinstance(msg, dict):
                    role = msg.get('role')
                    # Try to get content from either 'content' or 'message' key
                    content = msg.get('content') or msg.get('message')
                    
                    if role and content:
                        filtered_messages.append({'role': role, 'content': content})
                        
            # Log the message processing results
            print(f"[DEBUG] Processed {len(chat_history)} messages into {len(filtered_messages)} filtered messages")
            
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
            - phoneNumber: Customer's phone number with country code without any spaces or dashes
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
            session_key = request.GET.get('session_key')
            action = request.GET.get('action')
            
            if action == 'get_messages' and (client_phone_number or session_key):
                # Get all messages for this chat
                messages = OpenAIAgent.get_chat_messages(client_phone_number, session_key)
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
        session_key = data.get('session_key')
        message_text = data.get('message')
        
        print(f"\n[DEBUG] Chat API request")
        print(f"[DEBUG] Business ID: {business_id}")
        print(f"[DEBUG] Client phone number: {client_phone_number}")
        print(f"[DEBUG] Message: {message_text}")
        
        # Validate required fields
        if not business_id or not (client_phone_number or session_key) or not message_text:
            return JsonResponse({
                'error': 'Missing required fields'
            }, status=400)
        
        # Get or create the chat
        chat = OpenAIAgent.get_or_create_chat(business_id, client_phone_number, session_key)
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
        messages = OpenAIAgent.get_chat_messages(client_phone_number, session_key)
        
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
            business = Business.objects.get(businessId=business_id)
            ai_response = OpenAIAgent.process_ai_response(response, client_phone_number, business)
            
            # Save the assistant message - only if ai_response is not None or empty
            if ai_response:
                # Create a new message for the assistant response
                Messages.objects.create(
                    chat=chat,
                    role='assistant',
                    message=ai_response['content']
                )

                # Add the assistant message to formatted_messages for summary extraction
                formatted_messages.append({
                    'role': 'assistant',
                    'content': ai_response['content']
                })
                
                # Process tool call results if any
                if 'tool_call_results' in ai_response and ai_response['tool_call_results']:
                    print(f"[DEBUG] Processing {len(ai_response['tool_call_results'])} tool call results")
                    
                    # Create tool messages for each tool call result
                    for tool_result in ai_response['tool_call_results']:
                        try:
                            # Save the tool message to the database
                            Messages.objects.create(
                                chat=chat,
                                role='tool',
                                message=tool_result['result']
                            )
                            
                            # Add the tool message to formatted_messages
                            formatted_messages.append({
                                'role': 'tool',
                                'content': tool_result['result']
                            })
                        except Exception as e:
                            print(f"[ERROR] Error saving tool message: {str(e)}")
                            traceback.print_exc()
            else:
                # Handle case where ai_response is None or empty
                print("[DEBUG] Empty AI response")
                Messages.objects.create(
                    chat=chat,
                    role='assistant',
                    message="I'm sorry, I encountered an error processing your request. Please try again."
                )
            
            # Analyze and update chat summary
            # Make sure formatted_messages is in the correct format
            # Each message should be a dictionary with 'role' and 'content' keys
            messages_for_summary = []
            
            # Convert all messages to the correct format
            for msg in formatted_messages:
                if isinstance(msg, dict) and 'role' in msg:
                    # Handle both 'content' and 'message' keys
                    content = msg.get('content') or msg.get('message')
                    if content:  # Only add messages with content
                        messages_for_summary.append({
                            'role': msg['role'],
                            'content': content
                        })
          
            # Extract conversation summary if we have enough messages
            if len(messages_for_summary) >= 2:
                try:
                    # Extract conversation summary
                    summary = OpenAIAgent.extract_conversation_summary(messages_for_summary)
                    
                    # Update chat summary in database
                    # Make sure we're storing the summary as a JSON string
                    if isinstance(summary, dict):
                        chat.summary = summary
                        chat.save()
                        print(f"[DEBUG] Successfully saved summary to chat: {len(summary.keys())} fields")
                    else:
                        print(f"[DEBUG] Summary is not a dict, cannot save: {type(summary)}")
                except Exception as e:
                    print(f"Error extracting conversation summary: {str(e)}")
                    traceback.print_exc()
            
            # Return the response
            response_data = {
                'response': ai_response.get('content', '')
            }
            
            # Add original content if available
            if 'original_content' in ai_response:
                response_data['original_content'] = ai_response['original_content']
            
            # Add tool call results if any
            if 'tool_call_results' in ai_response and ai_response['tool_call_results']:
                response_data['tool_call_results'] = ai_response['tool_call_results']
            
            # Add error if any
            if 'error' in ai_response:
                response_data['error'] = ai_response['error']
            
            return JsonResponse(response_data)
            
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