from django.db.models import Q
from datetime import datetime
import pytz
from dotenv import load_dotenv
import os
from openai import OpenAI
import traceback
import re

load_dotenv()

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
# Change timezone to chicago
current_time = datetime.now().astimezone(pytz.timezone('America/Chicago'))



def find_by_phone_number(model, field_name, phone):
    """Find a record by trying different phone number formats."""

    # Extract only the last 10 digits for a more reliable comparison
    phone_digits = re.sub(r'\D', '', phone)  # Remove all non-numeric characters
    phone_last_10 = phone_digits[-10:]  # Get the last 10 digits
    
    # Build query to check different formats in a single database hit
    query = Q(**{field_name: phone}) | Q(**{field_name: phone_digits}) | Q(**{field_name: phone_last_10})
    
    return model.objects.filter(query).first()






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


def format_messages_for_openai(messages, system_prompt):
    """Format chat messages for OpenAI API"""
    formatted_messages = [{"role": "system", "content": system_prompt}]
    
    for message in messages:
        if hasattr(message, 'role'):
            # Handle Messages objects
            role = message.role
            content = message.message
            
            # Convert tool messages to assistant messages
            if role == 'tool':
                # If it's a JSON string, leave it as is, otherwise stringify it
                if not isinstance(content, str) or (isinstance(content, str) and not content.startswith('{')):
                    content = f"Tool Response: {str(content)}"
                formatted_messages.append({
                    "role": "assistant",
                    "content": content
                })
            else:
                formatted_messages.append({"role": role, "content": content})
        elif isinstance(message, dict):
            # Handle dictionary messages
            role = message.get('role')
            content = message.get('content') or message.get('message')
            
            if role and content:
                # Convert tool messages to assistant messages
                if role == 'tool':
                    # If it's a JSON string, leave it as is, otherwise stringify it
                    if not isinstance(content, str) or (isinstance(content, str) and not content.startswith('{')):
                        content = f"Tool Response: {str(content)}"
                    formatted_messages.append({
                        "role": "assistant",
                        "content": content
                    })
                else:
                    formatted_messages.append({"role": role, "content": content})
    
    return formatted_messages


def get_chat_status(chat):
    """
    Use OpenAI to analyze a chat and determine its status
    """
    try:
        # Get chat messages directly from database
        from .models import Messages
        messages = Messages.objects.filter(chat=chat).order_by('createdAt')
        
        if not messages.exists():
            return "pending"
        
        # Format messages for OpenAI
        SYSTEM_PROMPT = """
        You are an AI assistant that analyzes conversations and returns their status using a single-word response.

        Instructions:
        Analyze the conversation and determine its current status.
        Respond with only one word from the predefined list below.
        Do not add any extra text, explanations, or formatting.
        Allowed Responses:
        pending → Conversation is ongoing, and not respondeded.
        booked → If the user has confirmed a booking no matter conversation is ongoing or not.
        not_interested → The user is not interested.
       
        Example Outputs:
        If the conversation is unresolved → pending
        If the user confirms a booking → booked
        If the user expresses disinterest → not_interested
        If booking is confirmed → booked
        
        Important Rules:
        ✅ Return only one word from the list.
        ❌ Do not generate full sentences, explanations, or additional text.
        """
        
        formatted_messages = format_messages_for_openai(messages, SYSTEM_PROMPT)

        
        # Call OpenAI API
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=formatted_messages
            )
            
            response_text = response.choices[0].message.content.strip().lower()
            
            # Validate the response is one of the expected values
            valid_statuses = ["pending", "booked", "not_interested"]
            if response_text not in valid_statuses:
                response_text = "pending"
                
            chat.status = response_text
            chat.save()
            return response_text
            
        except Exception as e:
            print(f"[UTIL] Error getting chat status from OpenAI: {str(e)}")
            print(traceback.format_exc())
            return "error"
            
    except Exception as e:
        print(f"[UTIL] Error in get_chat_status: {str(e)}")
        print(traceback.format_exc())
        return "error"