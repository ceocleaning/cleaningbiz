from accounts.models import Business, ApiCredential



def get_retell_prompt(business):
    api_credential = ApiCredential.objects.filter(business=business).first()
    business_id = api_credential.business_id

    default_prompt = """
    ###Persona of AI Voice Agent
    Your name is Sarah, Office Assistant for CEO Cleaners from Dallas. Your role is to book appointment and answer client questions about cleaning services.

    ##Skills:
    - Professional and friendly communication
    - Efficient data collection and processing
    - Knowledgeable about CEO Cleaners' services and policies
    - Ability to check real-time calendar availability
    - Proficient in making service recommendations based on client needs

    ##Role: To assist clients in scheduling cleaning services seamlessly, ensuring all necessary information is collected and providing recommendations to enhance their experience.

    ##Objective: To facilitate a smooth and efficient booking process, ensuring client satisfaction and optimal scheduling for CEO Cleaners.

    ###Rules to Follow
    Always maintain a courteous and professional tone.
    Ensure clarity in communication; confirm details when necessary.
    Adhere to the data collection sequence outlined in the steps.
    Provide service recommendations based on client inputs.
    Verify calendar availability before confirming appointments.
    Offer alternative time slots if the preferred time is unavailable.
    Thank the client sincerely after booking.

    ##Addons
    - dishes
    - laundry
    - window
    - pets
    - fridge
    - oven
    - baseboard
    - blinds
    - green
    - cabinets
    - patio
    - garage

    ##Business TimeZone
    America/Chicago

    ##Business ID
    {business_id}

    ###Script AI has to Follow
    ##Greeting and Introduction:

    ##Initial Step
    - run {{current_time}} and convert it business timezone in the beginning of the call

    "Good [morning/afternoon/evening]! Thank you for contacting CEO Cleaners in Dallas. My name is Sarah,. How are you doing today?"
    Check for User's Intent:

    If the user expresses interest in booking a service:
    "Great! To proceed with your booking, may I have your full name, email address, and phone number?"
    Collect Client Information:

    Record the client's full name.
    Record the client's email address.
    Record the client's phone number.

    Gather Service Details:
    "Thank you, [Client's Name]. Could you please provide the area of your home in square feet that needs cleaning, including the number of bedrooms and bathrooms?"
    Record the specified areas, number of bedrooms, and bathrooms.

    Determine Service Type:
    Ask Which Service client is interested, We offer several cleaning services:
    Regular Cleaning,
    Deep Cleaning,
    Commercial Cleaning,
    Customized Cleaning , Which service would you prefer? Based on your previous responses, I recommend [Service Type] for optimal results."

    If user selects commercial cleaning 
    - run {{send_commercial_link}} 
    - After that {{end_call}}

    ##Ask for Addons
    - After getting service type ask the user he wants some addons

    - If user selects addons ask user to provide quantity of the selected addons

    - Confirm from user that here are your selected addons

    ##Ask for Additional Requests
    - Ask user if they additional requests or notes that we should know

    ##Collect Service Location:
    "Could you please provide the full address where the cleaning service is needed?"
    Record the client's address.

    ##Schedule Appointment:
    "Thank you. Please select your preferred date and time for the service. Our available time slots are from 9:00 AM to 5:00 PM, Central Standard Time (America/Chicago)."
    (wait for response)
    run {{check_availability}}

    If time is unavailable:
    "I'm sorry, but the selected time slot is not available. Here are three alternative options based on our current availability:
    [Alternative Date and Time 1]
    [Alternative Date and Time 2]
    [Alternative Date and Time 3] Please choose one of these, or let me know another time that works for you."

    ##After Collecting Preferred Date and Time:
    {{bookAppointment}} 

    ##Booking Confirmation:
    Upon successful booking, inform the client:
    "Your appointment has been successfully booked for [Confirmed Date and Time]. You will receive a confirmation email shortly."


    ##Closing:

    "Thank you, [Client's Name], for choosing CEO Cleaners. We look forward to providing you with exceptional service. Have a wonderful day!"

    {{end_call}}
    """.format(business_id=business_id)

    return default_prompt

def get_retell_tools(business):
    api_credential = ApiCredential.objects.filter(business=business).first()
    secretKey = api_credential.secretKey
    custom_tools = [
            {
                "type": "end_call",
                "name": "end_call",
                "description": "End the call with user."
            },
            {
                "type": "custom",
                "name": "check_availability",
                "description": "Check TimeSlot Availability of User Selected DateTime",
                "url": f"https://cleaningbizai.com/api/availability/{secretKey}/",
                "execution_message_description": "Checking TimeSlot Availability",
                "timeout_ms": 10000,
                "speak_during_execution": True,
                "speak_after_execution": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cleaningDateTime": {
                            "type": "string",
                            "description": "The ISO 8601 timestamp user selected date time (e.g., '2025-02-26T14:00:00+00:00')."
                        }
                    },
                    "required": ["cleaningDateTime"]
                }
            },
            {
                "type": "custom",
                "name": "send_commercial_link",
                "description": "This function will send email to client if client selects commercial cleaning service",
                "url": "https://cleaningbizai.com/api/send-commercial-form-link/",
                "execution_message_description": "Sending Commercial Cleaning Form Link",
                "timeout_ms": 10000,
                "speak_during_execution": True,
                "speak_after_execution": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Full Name of the Client"
                        },
                        "business_id": {
                            "type": "string",
                            "description": "Business ID"
                        },
                        "email": {
                            "type": "string",
                            "description": "Email of the Client"
                        }
                    },
                    "required": ["email", "name", "business_id"]
                }
            },
            {
                "type": "custom",
                "name": "bookAppointment",
                "description": "This will be used to book an appointment",
                "url": "https://cleaningbizai.com/api/create-booking/",
                "execution_message_description": "Booking Appointment",
                "timeout_ms": 10000,
                "speak_during_execution": True,
                "speak_after_execution": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pets": {
                            "type": "integer",
                            "description": "Qty for the pet cleaning add-on"
                        },
                        "fridge": {
                            "type": "integer",
                            "description": "Qty of fridge cleaning add-on"
                        },
                        "city": {
                            "type": "string",
                            "description": "The city where the service is booked."
                        },
                        "appointment_date_time": {
                            "type": "string",
                            "description": "The date and time when the cleaning service is scheduled."
                        },
                        "zip_code": {
                            "type": "string",
                            "description": "The postal code of the booking location."
                        },
                        "patio": {
                            "type": "integer",
                            "description": "Qty for the patio cleaning add-on"
                        },
                        "laundry": {
                            "type": "integer",
                            "description": "The number of laundry loads included as an add-on."
                        },
                        "baseboard": {
                            "type": "integer",
                            "description": "Qty of Baseboard add-on"
                        },
                        "state": {
                            "type": "string",
                            "description": "The state or province of the booking location."
                        },
                        "first_name": {
                            "type": "string",
                            "description": "The first name of the person making the booking."
                        },
                        "cabinets": {
                            "type": "integer",
                            "description": "Qty for the cabinets cleaning add-on"
                        },
                        "email": {
                            "type": "string",
                            "description": "The email address of the person making the booking."
                        },
                        "area": {
                            "type": "integer",
                            "description": "The total square footage of the location."
                        },
                        "blinds": {
                            "type": "integer",
                            "description": "Qty for blinds cleaning add-on"
                        },
                        "address": {
                            "type": "string",
                            "description": "Primary address for the booking."
                        },
                        "green": {
                            "type": "integer",
                            "description": "Qty for the green cleaning add-on"
                        },
                        "oven": {
                            "type": "integer",
                            "description": "Qty of oven cleaning add-on"
                        },
                        "garage": {
                            "type": "integer",
                            "description": "Qty for the garage cleaning add-on"
                        },
                        "last_name": {
                            "type": "string",
                            "description": "The last name of the person making the booking."
                        },
                        "dishes": {
                            "type": "integer",
                            "description": "The number of dish add-ons"
                        },
                        "bathrooms": {
                            "type": "integer",
                            "description": "The number of bathrooms in the booking location."
                        },
                        "windows": {
                            "type": "integer",
                            "description": "Qty for window cleaning add-on"
                        },
                        "bedrooms": {
                            "type": "integer",
                            "description": "The number of bedrooms in the booking location."
                        },
                        "service_type": {
                            "type": "string",
                            "description": "The type of cleaning service requested."
                        },
                        "phone_number": {
                            "type": "string",
                            "description": "The phone number of the person making the booking."
                        },
                        "business_id": {
                            "type": "string",
                            "description": "Business ID"
                        }
                    },
                    "required": [
                        "first_name", "last_name", "email", "phone_number", "address", "city", "state", 
                        "zip_code", "bedrooms", "bathrooms", "area", "service_type", "appointment_date_time", 
                        "business_id", "pets", "fridge", "patio", "laundry", "baseboard", "cabinets", 
                        "blinds", "green", "oven", "garage", "dishes", "windows"
                    ]
                }
            }
        ]
    
    return custom_tools