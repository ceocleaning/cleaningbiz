import re
import requests
from django.conf import settings

EMAILIT_API_KEY = settings.EMAILIT_API_KEY

def send_email(from_email, to_email, subject, reply_to=None, text_content='', attachments=None, html_content=None):
    """
    Send an email using the EmailIt API.

    Parameters:
    - from_email (str): The sender's email in format 'Business Name <user@example.com>'.
    - to_email (str or list): Recipient(s) email address.
    - subject (str): The subject of the email.
    - reply_to (str, optional): The reply-to email address.
    - text_content (str, optional): The plain text content of the email.
    - attachments (list of dict, optional): Attachments [{'filename': '...', 'content': '...', 'content_type': '...'}].
    """

    url = "https://api.emailit.com/v1/emails"
    req_headers = {
        "Authorization": f"Bearer {EMAILIT_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Normalize from_email
    default_domain = "cleaningbizai.com"
    pattern = r"^(.*?)<([^@<>]+)@([^@<>]+)>$"
    match = re.match(pattern, from_email.strip())

    if match:
        business_name, user, _ = match.groups()
        business_name = business_name.strip()
        from_email = f"{business_name} <{user}@{default_domain}>"
    else:
        # Fallback if invalid format
        from_email = f"CleaningBiz AI <noreply@{default_domain}>"

    data = {
        "from": from_email,
        "to": to_email,
        "subject": subject,
        "text": text_content
    }

    if html_content:
        data["html"] = html_content

    if reply_to:
        data["reply_to"] = reply_to
    if attachments:
        data["attachments"] = attachments

    if settings.DEBUG == False:
        try:
            response = requests.post(url, json=data, headers=req_headers)

            if response.status_code in [200, 201]:
                return {"success": True, "response": response.json()}
            else:
                print(response.text)

        except requests.exceptions.RequestException as e:
            print(f"Failed to send email: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status_code": getattr(e.response, "status_code", None),
                "response_text": getattr(e.response, "text", None)
        }

    else:
        return {"success": True, "response": "Email not sent in debug mode"}
