import google.generativeai as genai
from datetime import datetime
import pytz
from dotenv import load_dotenv
import os
from openai import OpenAI
import traceback

load_dotenv()

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
# Change timezone to chicago
current_time = datetime.now().astimezone(pytz.timezone('America/Chicago'))

def convert_date_str_to_date(date_str):
    SYSTEM_PROMPT = f"""
    You are a helpful assistant that can convert a human readable date string to a datetime object.
    
    Current time: {current_time}

    Takes any human readable date string and convert it to datetime object
    Return only single datetime object in string format

    example:
    Input: Tomorrow at 2 PM
    Output: 2025-03-12 14:00:00

    Input: Today at 10 AM
    Output: 2025-03-11 10:00:00

    Input: Next week monday at 3 PM
    Output: 2025-03-18 15:00:00

    Input: 13th mar at 10 am
    Output: 2025-03-13 10:00:00
    """
    
    formatted_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Date string: {date_str}"}
    ]
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=formatted_messages,
        temperature=0.1,
        max_tokens=100,
        top_p=0.95,
        top_k=40,
        )
    
    response_text = response.choices[0].message.content.strip()

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
        booked → The user has confirmed a booking.
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