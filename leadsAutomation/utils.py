from openai import api_key
import requests
from django.conf import settings

EMAILIT_API_KEY = settings.EMAILIT_API_KEY

def send_email(from_email, to_email, reply_to, subject, html_body, text_content):
    """
    Send an email using the EmailIt API.

    Parameters:
    - from_email (str): The sender's email address.
    - to_email (str): The recipient's email address.
    - subject (str): The subject of the email.
    - html_body (str): The HTML content of the email.
    """
    url = 'https://api.emailit.com/v1/emails'
    headers = {
        'Authorization': f'Bearer {EMAILIT_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        'from': from_email,
        'to': to_email,
        'reply_to': reply_to,
        'subject': subject,
        'html': html_body,
        'text': text_content
    }

    response = requests.post(url, json=data, headers=headers)

    return response.json()