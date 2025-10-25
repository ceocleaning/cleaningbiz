from django.db.models import Q
from datetime import datetime
import pytz
from dotenv import load_dotenv
from accounts.models import Business, BusinessSettings, CustomAddons
import os
from openai import OpenAI
import traceback
import re

load_dotenv()

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
# Change timezone to chicago
current_time = datetime.now().astimezone(pytz.timezone('America/Chicago'))



def find_by_phone_number(model, field_name, phone, business):
    """Find a record by trying different phone number formats."""

    # Extract only the last 10 digits for a more reliable comparison
    phone_digits = re.sub(r'\D', '', phone)  # Remove all non-numeric characters
    phone_last_10 = phone_digits[-10:]  # Get the last 10 digits
    
    # Build query to check different formats in a single database hit
    query = Q(**{field_name: phone}) | Q(**{field_name: phone_digits}) | Q(**{field_name: phone_last_10})
    
    return model.objects.filter(business=business).filter(query).first()


def default_prompt(business):
    try:
        business_settings = business.settings
        custom_addons = business.business_custom_addons

        # Define pricing fields by category
        base_pricing = {
            'Bedroom Price': f"${business_settings.bedroomPrice}",
            'Bathroom Price': f"${business_settings.bathroomPrice}",
            'Deposit Fee': f"${business_settings.depositFee}",
            'Tax Percent': f"{business_settings.taxPercent}%"
        }
        
        multipliers = {
            'Standard': f"${business_settings.sqftMultiplierStandard}",
            'Deep': f"${business_settings.sqftMultiplierDeep}",
            'Moveinout': f"${business_settings.sqftMultiplierMoveinout}",
            'Airbnb': f"${business_settings.sqftMultiplierAirbnb}"
        }
        
        addons = {
            'Dishes': f"${business_settings.addonPriceDishes}",
            'Laundry': f"${business_settings.addonPriceLaundry}",
            'Window': f"${business_settings.addonPriceWindow}",
            'Pets': f"${business_settings.addonPricePets}",
            'Fridge': f"${business_settings.addonPriceFridge}",
            'Oven': f"${business_settings.addonPriceOven}",
            'Baseboard': f"${business_settings.addonPriceBaseboard}",
            'Blinds': f"${business_settings.addonPriceBlinds}",
            'Green': f"${business_settings.addonPriceGreen}",
            'Cabinets': f"${business_settings.addonPriceCabinets}",
            'Patio': f"${business_settings.addonPricePatio}",
            'Garage': f"${business_settings.addonPriceGarage}"
        }
        
        # Build the pricing sections
        sections = ['#PRICINGS\n']
        
        # Filter non-zero values and format them
        non_zero_base = {k: v for k, v in base_pricing.items() if v}
        if non_zero_base:
            sections.extend([f"{k}: {v}" for k, v in non_zero_base.items()])
        
        non_zero_multipliers = {k: v for k, v in multipliers.items() if v}
        if non_zero_multipliers:
            sections.append('\n# Square Feet Multipliers')
            sections.extend([f"{k}: {v}" for k, v in non_zero_multipliers.items()])
        
        non_zero_addons = {k: v for k, v in addons.items() if v}
        if non_zero_addons:
            sections.append('\n# Add-on Prices')
            sections.extend([f"{k}: {v}" for k, v in non_zero_addons.items()])
        
        # Join all sections with proper formatting
        business_pricings = "    " + "\n    ".join(sections)

  
        prompt = f"""
## 🎯 Role of the AI SMS Agent
The AI SMS Agent acts as a friendly, professional, and persuasive virtual assistant for **{business.businessName}**.  
It manages inbound and outbound SMS conversations to:

- Greet and engage potential customers  
- Confirm interest in cleaning services  
- Collect essential customer details (name, phone, email, address)  
- Gather property details (square footage, bedrooms, bathrooms, add-ons)  
- Present service options and pricing  
- Schedule and confirm cleaning appointments  
- Send booking confirmations and invoice links via SMS or email  

The goal is to ensure a **smooth, helpful, and persuasive booking experience** that converts leads into confirmed appointments.

---

## 🏢 About {business.businessName}
**{business.businessName}** is a professional cleaning company based in **{business.address}**.  
They specialize in providing both residential and commercial cleaning solutions that fit the specific needs of each client.

### Mission
- Deliver reliable, high-quality, and customized cleaning services  
- Maintain clean, healthy, and comfortable environments for clients  
- Achieve 100% customer satisfaction through professionalism and care  

---

## 🧹 Services Offered
- **Regular Cleaning:** Routine maintenance for homes or apartments  
- **Deep Cleaning:** Intensive top-to-bottom cleaning (recommended for first-time or seasonal)  
- **Commercial Cleaning:** Offices, business spaces, and work environments  

---

## 💲 Pricing (All prices in USD)
{business_pricings}

---

## 💬 SMS Conversation Flow

### 1. Greeting & Engagement
Start by greeting the customer naturally and introducing {business.businessName}.  
Offer help and ask if they’d like to book a cleaning appointment.

Example tone:
> Hi there! This is Sarah from {business.businessName}. Hope you're doing well today.  
> I’d love to help get your space sparkling clean — would you like to schedule a cleaning service?

---

### 2. Confirm Interest & Collect Basic Info
If the customer shows interest:
- Ask for their **full name**  
- Ask for their **phone number**  
- Ask for their **email address** (to send the booking confirmation)

Pause and confirm each piece of info before moving forward.

---

### 3. Property Details
Ask for:
- Approximate **square footage** of the property  
- Number of **bedrooms**  
- Number of **bathrooms**

Then ask if they want to include any **add-ons**, and provide the list available from the pricing data.

Example:
> Would you like to add window, oven, fridge, or garage cleaning?  
> Please mention which ones and how many.

---

### 4. Cleaning Type
Explain available cleaning types briefly:
- Regular Cleaning – Standard home maintenance cleaning  
- Deep Cleaning – Detailed cleaning (recommended for first-time or seasonal cleaning)  

Ask which one the customer would like to book.

---

### 5. Quotation
Once all details are available, calculate the estimated total cost:
**Formula:**  


Present the total naturally and confidently.  
If the customer hesitates, offer a small perk (e.g. free oven cleaning or a first-time discount).

---

### 6. Address & Scheduling
Request:
- The **full address** where cleaning will take place  
- The **preferred date and time** for the appointment  

If the requested slot isn’t available, provide 3 alternate time slots and let the customer choose one.

---

### 7. Booking Confirmation
Once confirmed:
- Tell the customer you’re adding the booking to the system.  
- Send a link via SMS or email to confirm and pay the invoice.  
- Let them know payment secures their appointment slot.  

Close warmly:
> Thank you for choosing {business.businessName}!  
> We look forward to making your space shine.

---

## 🤖 AI Agent Behavior Guidelines
- Maintain a **friendly, confident, and conversational** tone  
- Use short, clear messages suited for SMS  
- Wait for responses before continuing  
- Confirm every key detail (contact info, address, date, type, price)  
- Encourage hesitant customers with friendly incentives  
- Always close interactions positively  

---

## 💡 Example Summary Flow
1. Greet and engage  
2. Confirm interest  
3. Collect name, phone, email  
4. Gather property details  
5. Offer add-ons  
6. Select cleaning type  
7. Present quote  
8. Collect address  
9. Schedule date and time  
10. Send invoice and confirm booking  
11. Thank the customer  

---

**End of Prompt**
"""
        return prompt


    
    except Exception as e:
        print(f"Error generating Default Prompt: {e}")
        return None






def convert_date_str_to_date(date_str, business=None):
    # Get the business timezone if provided, otherwise use Chicago timezone as default
    timezone_str = 'America/Chicago'
    if business:
        try:
            timezone_str = business.get_timezone()
        except:
            pass
    
    # Get current time in the business timezone
    if not business:
        business_time = datetime.now()   
    else:
        business_time = business.get_local_time()
    
    SYSTEM_PROMPT = f"""
    You are a helpful assistant that can convert any date and time format to a standardized datetime object.
    
    Current time in {timezone_str}: {business_time}

    Takes any human readable date string or any datetime format string and convert it to datetime object.
    Return only single datetime object in string format (YYYY-MM-DD HH:MM:SS).
    
    Important rules:
    - If no time is provided, use 00:00:00 as the default time
    - Handle both US (M/D/YYYY) and international (D/M/YYYY) date formats intelligently
    - Support natural language dates including ordinals (e.g., "7th of April, 2025")
    - Parse relative dates like "tomorrow", "next week", "in 3 days"
    - Always return in YYYY-MM-DD HH:MM:SS format in {timezone_str} timezone
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

    print(f"[UTIL] Converted {date_str} to datetime object: {response_text} in timezone {timezone_str}")

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