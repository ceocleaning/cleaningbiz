from django.db.models import Q
from datetime import datetime
import pytz
from dotenv import load_dotenv
import os
import json
from openai import OpenAI


load_dotenv()

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
# Change timezone to chicago
current_time = datetime.now().astimezone(pytz.timezone('America/Chicago'))

def convert_date_str_to_date(date_str):
    SYSTEM_PROMPT = f"""
    You are a helpful assistant that can convert any date and time format to a standardized datetime object.
    
    Current time: {current_time}

    Takes any human readable date string or any datetime format string and convert it to datetime object.
    Return only single datetime object in string format (YYYY-MM-DD HH:MM:SS).
    
    Important rules:
    - If no time is provided, use 00:00:00 as the default time
    - Handle both US (M/D/YYYY) and international (D/M/YYYY) date formats intelligently
    - Support natural language dates including ordinals (e.g., "7th of April, 2025")
    - Parse relative dates like "tomorrow", "next week", "in 3 days"
    - Always return in YYYY-MM-DD HH:MM:SS format
    - Do not include any explanations, only return the formatted datetime

    example:
    Input: Tomorrow at 2 PM
    Output: 2025-03-12 14:00:00

    Input: Today at 10 AM
    Output: 2025-03-11 10:00:00

    Input: Next week monday at 3 PM
    Output: 2025-03-18 15:00:00

    Input: 13th mar at 10 am
    Output: 2025-03-13 10:00:00
    
    Input: 4/7/2025
    Output: 2025-04-07 00:00:00
    
    Input: 7th of April, 2025
    Output: 2025-04-07 00:00:00
    
    Input: 12-25-2025
    Output: 2025-12-25 00:00:00
    
    Input: April 7
    Output: 2025-04-07 00:00:00
    """
    
    formatted_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Date string: {date_str}"}
    ]
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=formatted_messages,
        temperature=0.1,
        max_tokens=100
        )
    
    response_text = response.choices[0].message.content.strip()

    print(f"[UTIL] Converted {date_str} to datetime object: {response_text}")

    return response_text

def extract_client_info_from_conversation(conversation, industry=None):
    """
    Extract client information from a conversation using OpenAI.
    
    Args:
        conversation: List of conversation messages or string of conversation text
        industry: Optional industry type to customize extraction fields
    
    Returns:
        dict: Extracted client information
    """
    # Convert conversation to text if it's a list of messages
    if isinstance(conversation, list):
        conversation_text = "\n".join([f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" 
                                     for msg in conversation if msg.get('content')])
    else:
        conversation_text = conversation
    
    # Base extraction fields for all industries
    base_fields = [
        "Client name",
        "Client phone number",
        "Client email",
        "Service they're interested in",
        "Preferred appointment date (in YYYY-MM-DD format)",
        "Preferred appointment time (in HH:MM format)"
    ]
    
    # Add industry-specific fields
    industry_fields = {
        "cleaning": [
            "Property size (square footage)",
            "Property type (house, apartment, office)",
            "Special cleaning requirements"
        ],
        "real_estate": [
            "Consultation type (buying, selling, investment)",
            "Property type of interest",
            "First-time buyer status",
            "Urgency level"
        ],
        "wellness": [
            "Health concerns",
            "Previous treatments",
            "Allergies or sensitivities"
        ],
        "home_services": [
            "Property age",
            "Urgency level",
            "Previous service history"
        ]
    }
    
    # Combine base fields with industry-specific fields
    extraction_fields = base_fields
    if industry and industry.lower() in industry_fields:
        extraction_fields.extend(industry_fields[industry.lower()])
    
    # Create the extraction prompt
    extraction_prompt = f"""
    Please extract the following information from the conversation if available:
    {chr(10).join([f"{i+1}. {field}" for i, field in enumerate(extraction_fields)])}
    
    Only include information that is explicitly mentioned in the conversation.
    Return the information in JSON format with the following keys:
    {", ".join([field.lower().replace(" ", "_").replace("(", "").replace(")", "") for field in extraction_fields])}
    
    For dates and times, extract them EXACTLY as mentioned by the user, without converting to any standard format.
    For example, if the user says "tomorrow at 2pm", return "tomorrow at 2pm" not a formatted date.
    
    If any information is not available, set the value to null.
    """
    
    # Format messages for OpenAI
    formatted_messages = [
        {"role": "system", "content": "You are a helpful assistant that extracts specific information from conversations."},
        {"role": "user", "content": f"Conversation:\n{conversation_text}\n\n{extraction_prompt}"}
    ]
    
    # Call OpenAI API
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=formatted_messages,
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    
    # Parse and return the response
    try:
        extraction_result = json.loads(response.choices[0].message.content)
        
        # Make sure all values are JSON serializable
        json_safe_result = {}
        for key, value in extraction_result.items():
            if value is None or isinstance(value, (str, int, float, bool, list, dict)):
                json_safe_result[key] = value
            else:
                # Convert non-serializable objects to strings
                json_safe_result[key] = str(value)
        
        print(f"[UTIL] Extracted client info: {json_safe_result}")
        return json_safe_result
    except Exception as e:
        print(f"[UTIL] Error extracting client info: {e}")
        return {"error": str(e)}

def extract_service_details_from_text(text, business_services):
    """
    Match mentioned services in text to actual business services.
    
    Args:
        text: Text to analyze for service mentions
        business_services: List of service objects from the business
    
    Returns:
        dict: Matched services with details
    """
    # Format the business services for the prompt
    services_text = "\n".join([f"- {service.name}: ${service.price} - {service.duration} minutes" 
                             for service in business_services])
    
    # Create the extraction prompt
    extraction_prompt = f"""
    Below is a list of services offered by the business:
    {services_text}
    
    Please identify which services are mentioned or requested in the following text:
    "{text}"
    
    Return the results in JSON format with the following structure:
    {{
        "matched_services": [
            {{
                "service_name": "Name of the matched service",
                "confidence": 0.95 // A number between 0 and 1 indicating confidence level
            }}
        ],
        "quantity": 1 // The number of services requested, default to 1 if not specified
    }}
    
    Only include services that are explicitly or implicitly mentioned in the text.
    If no services are mentioned, return an empty array for matched_services.
    """
    
    # Format messages for OpenAI
    formatted_messages = [
        {"role": "system", "content": "You are a helpful assistant that matches service mentions to actual business services."},
        {"role": "user", "content": extraction_prompt}
    ]
    
    # Call OpenAI API
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=formatted_messages,
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    
    # Parse and return the response
    try:
        extraction_result = json.loads(response.choices[0].message.content)
        
        # Make sure all values are JSON serializable
        json_safe_result = {}
        for key, value in extraction_result.items():
            if isinstance(value, list):
                # Handle lists (like matched_services)
                json_safe_list = []
                for item in value:
                    if isinstance(item, dict):
                        # Handle dictionaries within lists
                        json_safe_dict = {}
                        for k, v in item.items():
                            if v is None or isinstance(v, (str, int, float, bool)):
                                json_safe_dict[k] = v
                            else:
                                json_safe_dict[k] = str(v)
                        json_safe_list.append(json_safe_dict)
                    else:
                        # Handle primitive values in lists
                        if item is None or isinstance(item, (str, int, float, bool)):
                            json_safe_list.append(item)
                        else:
                            json_safe_list.append(str(item))
                json_safe_result[key] = json_safe_list
            elif value is None or isinstance(value, (str, int, float, bool, dict)):
                json_safe_result[key] = value
            else:
                # Convert non-serializable objects to strings
                json_safe_result[key] = str(value)
        
        print(f"[UTIL] Extracted service details: {json_safe_result}")
        return json_safe_result
    except Exception as e:
        print(f"[UTIL] Error extracting service details: {e}")
        return {"matched_services": [], "error": str(e)}

# LangChain Agent Utilities
def get_or_create_langchain_agent(business_id, phone_number=None, session_key=None, chat_id=None):
    """
    Get or create a LangChain agent for a business.
    
    Args:
        business_id: ID of the business
        phone_number: Optional phone number for SMS-based chats
        session_key: Optional session key for web-based chats
        chat_id: Optional chat ID to continue an existing conversation
        
    Returns:
        LangChainAgent instance
    """
    from .langchain_agent import LangChainAgent
    
    try:
        # Create a new agent instance
        agent = LangChainAgent(
            business_id=business_id,
            chat_id=chat_id,
            phone_number=phone_number,
            session_key=session_key
        )
        return agent
    except Exception as e:
        print(f"[UTIL] Error creating LangChain agent: {e}")
        return None

def process_sms_with_langchain(business_id, phone_number, message_text):
    """
    Process an incoming SMS message using the LangChain agent.
    
    Args:
        business_id: ID of the business
        phone_number: Phone number of the sender
        message_text: Text content of the message
        
    Returns:
        str: Response from the agent
    """
    try:
        # Get or create agent
        agent = get_or_create_langchain_agent(
            business_id=business_id,
            phone_number=phone_number
        )
        
        if not agent:
            return "Sorry, we're experiencing technical difficulties. Please try again later."
        
        # Process the message
        response = agent.process_message(message_text)
        
        # Update chat summary
        agent.update_chat_summary()
        
        return response
    except Exception as e:
        print(f"[UTIL] Error processing SMS with LangChain: {e}")
        return "Sorry, we're experiencing technical difficulties. Please try again later."

def process_web_chat_with_langchain(business_id, session_key, message_text):
    """
    Process a web chat message using the LangChain agent.
    
    Args:
        business_id: ID of the business
        session_key: Session key for the web chat
        message_text: Text content of the message
        
    Returns:
        str: Response from the agent
    """
    try:
        # Get or create agent
        agent = get_or_create_langchain_agent(
            business_id=business_id,
            session_key=session_key
        )
        
        if not agent:
            return "Sorry, we're experiencing technical difficulties. Please try again later."
        
        # Process the message
        response = agent.process_message(message_text)
        
        # Update chat summary
        agent.update_chat_summary()
        
        return response
    except Exception as e:
        print(f"[UTIL] Error processing web chat with LangChain: {e}")
        return "Sorry, we're experiencing technical difficulties. Please try again later."


