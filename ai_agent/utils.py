import google.generativeai as genai
from datetime import datetime
import pytz
from dotenv import load_dotenv
import os

load_dotenv()


# Initialize Google Gemini AI
genai.configure(api_key=os.getenv('GEMENI_API'))
model = genai.GenerativeModel('gemini-2.0-flash')
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
        {"role": "model", "parts": [{"text": SYSTEM_PROMPT}]},
        {"role": "user", "parts": [{"text": f"Date string: {date_str}"}]}
    ]
    
    response = model.generate_content(
        formatted_messages,
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,
            max_output_tokens=100,
            top_p=0.95,
            top_k=40,
        )
    )
    
    print(f"[DEBUG] String Date to DateTime - UTIL Function: {response.text}")
    return response.text

