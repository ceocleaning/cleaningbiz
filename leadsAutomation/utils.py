import requests
from django.conf import settings

EMAILIT_API_KEY = settings.EMAILIT_API_KEY

def send_email(from_email, to_email, subject, reply_to=None, html_body='', text_content='', attachments=None):
    """
    Send an email using the EmailIt API.

    Parameters:
    - from_email (str): The sender's email address.
    - to_email (str): The recipient's email address.
    - subject (str): The subject of the email.
    - reply_to (str, optional): The reply-to email address.
    - html_body (str, optional): The HTML content of the email.
    - text_content (str, optional): The plain text content of the email.
    - attachments (list of dict, optional): Attachments [{'filename': '...', 'content': '...', 'content_type': '...'}].
    """
    url = 'https://api.emailit.com/v1/emails'
    req_headers = {
        'Authorization': f'Bearer {EMAILIT_API_KEY}',
        'Content-Type': 'application/json'
    }

    data = {
        'from': from_email,
        'to': to_email,
        'subject': subject,
        'html': html_body,
        'text': text_content
    }

    if reply_to:
        data['reply_to'] = reply_to
    if attachments:
        data['attachments'] = attachments


    response = requests.post(url, json=data, headers=req_headers)

    try:
        return response.json()
    except ValueError:
        print(response.text)
        print(response.status_code)
        return {
            'success': False,
            'error': f'Invalid JSON response. Status code: {response.status_code}',
            'response_text': response.text
        }
