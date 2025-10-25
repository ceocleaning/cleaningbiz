from accounts.models import Business, ApiCredential, CustomAddons

def get_all_active_addons(business):
    """
    Consolidates all active add-ons for a business into a single list.
    """
    active_addons = []
    pricing_obj = business.settings
    
    # Hardcoded addons
    if pricing_obj.addonPriceDishes > 0:
        active_addons.append({"name": "dishes", "data_name": "dishes", "price": f"${pricing_obj.addonPriceDishes}"})
    if pricing_obj.addonPriceLaundry > 0:
        active_addons.append({"name": "laundry", "data_name": "laundry", "price": f"${pricing_obj.addonPriceLaundry}"})
    if pricing_obj.addonPriceWindow > 0:
        active_addons.append({"name": "window", "data_name": "windows", "price": f"${pricing_obj.addonPriceWindow}"})
    if pricing_obj.addonPricePets > 0:
        active_addons.append({"name": "pets", "data_name": "pets", "price": f"${pricing_obj.addonPricePets}"})
    if pricing_obj.addonPriceFridge > 0:
        active_addons.append({"name": "fridge", "data_name": "fridge", "price": f"${pricing_obj.addonPriceFridge}"})
    if pricing_obj.addonPriceOven > 0:
        active_addons.append({"name": "oven", "data_name": "oven", "price": f"${pricing_obj.addonPriceOven}"})
    if pricing_obj.addonPriceBaseboard > 0:
        active_addons.append({"name": "baseboard", "data_name": "baseboard", "price": f"${pricing_obj.addonPriceBaseboard}"})
    if pricing_obj.addonPriceBlinds > 0:
        active_addons.append({"name": "blinds", "data_name": "blinds", "price": f"${pricing_obj.addonPriceBlinds}"})
    if pricing_obj.addonPriceGreen > 0:
        active_addons.append({"name": "green", "data_name": "green", "price": f"${pricing_obj.addonPriceGreen}"})
    if pricing_obj.addonPriceCabinets > 0:
        active_addons.append({"name": "cabinets", "data_name": "cabinets", "price": f"${pricing_obj.addonPriceCabinets}"})
    if pricing_obj.addonPricePatio > 0:
        active_addons.append({"name": "patio", "data_name": "patio", "price": f"${pricing_obj.addinPricePatio}"})
    if pricing_obj.addonPriceGarage > 0:
        active_addons.append({"name": "garage", "data_name": "garage", "price": f"${pricing_obj.addonPriceGarage}"})
        
    # Custom addons
    custom_addons = CustomAddons.objects.filter(business=business)
    for addon in custom_addons:
        active_addons.append({"name": addon.addonName, "data_name": addon.addonDataName, "price": f"${addon.addonPrice}"})
        
    return active_addons


def get_retell_prompt(business):
    api_credential = ApiCredential.objects.filter(business=business).first()
    business_obj = api_credential.business
    pricing_obj = business_obj.settings
    all_addons = get_all_active_addons(business_obj)
    addons_prompt_list = "\n".join([f"- {addon['name']}" for addon in all_addons])

    # Get active services
    active_services = []
    if pricing_obj.sqftMultiplierStandard > 0:
        active_services.append("Standard")
    if pricing_obj.sqftMultiplierDeep > 0:
        active_services.append("Deep Cleaning")
    if pricing_obj.sqftMultiplierMoveinout > 0:
        active_services.append("Moveinout")
    if pricing_obj.sqftMultiplierAirbnb > 0:
        active_services.append("Airbnb")
    
    services_list = "\n".join([f"- {service}" for service in active_services])

    # commercial_cleaning_prompt = f"""
    # If user selects commercial cleaning 
    # - run {{send_commercial_link}} 
    # - After that {{end_call}}
    # """ if pricing_obj.sqftMultiplierCommercial > 0 else ""

    default_prompt = f"""
###Persona of AI Voice Agent
Your name is Sarah, Office Assistant for {business_obj.businessName}. Your role is to book appointment and answer client questions about cleaning services.

##Skills:
- Professional and friendly communication
- Efficient data collection and processing
- Knowledgeable about {business_obj.businessName}'s services and policies
- Ability to check real-time calendar availability
- Proficient in making service recommendations based on client needs

##Role: To assist clients in scheduling cleaning services seamlessly, ensuring all necessary information is collected and providing recommendations to enhance their experience.

##Objective: To facilitate a smooth and efficient booking process, ensuring client satisfaction and optimal scheduling for {business_obj.businessName}.

###Rules to Follow
Always maintain a courteous and professional tone.
Ensure clarity in communication; confirm details when necessary.
Adhere to the data collection sequence outlined in the steps.
Provide service recommendations based on client inputs.
Verify calendar availability before confirming appointments.
Offer alternative time slots if the preferred time is unavailable.
Thank the client sincerely after booking.

##Addons
{addons_prompt_list}

##Business TimeZone
{business_obj.timezone}

##Business ID
{business_obj.businessId}

###Script AI has to Follow
##Greeting and Introduction:

##Initial Step
- run {{current_time}} and convert it business timezone in the beginning of the call

"Hi! Thank you for contacting {business_obj.businessName}. My name is Sarah,. How are you doing today?"

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
{services_list}

Which service would you prefer? Based on your previous responses, I recommend [Service Type] for optimal results."


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
"Thank you. Please select your preferred date and time for the service."
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

"Thank you, [Client's Name], for choosing {business_obj.businessName}. We look forward to providing you with exceptional service. Have a wonderful day!"

{{end_call}}
    """
    return default_prompt

#---

def get_book_appointment_tool_properties(business):
    """
    Dynamically generates the properties for the bookAppointment tool based on active addons.
    """
    all_addons = get_all_active_addons(business)
    properties = {
        "city": {
            "type": "string",
            "description": "The city where the service is booked."
        },
        "appointment_date_time": {
            "type": "string",
            "description": "The ISO 8601 timestamp user selected date time (e.g., '2025-02-26T14:00:00+00:00')."
        },
        "zip_code": {
            "type": "string",
            "description": "The postal code of the booking location."
        },
        "state": {
            "type": "string",
            "description": "The state or province of the booking location."
        },
        "first_name": {
            "type": "string",
            "description": "The first name of the person making the booking."
        },
        "email": {
            "type": "string",
            "description": "The email address of the person making the booking."
        },
        "area": {
            "type": "integer",
            "description": "The total square footage of the location."
        },
        "address": {
            "type": "string",
            "description": "Primary address for the booking."
        },
        "last_name": {
            "type": "string",
            "description": "The last name of the person making the booking."
        },
        "bathrooms": {
            "type": "integer",
            "description": "The number of bathrooms in the booking location."
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
    }

    # Add properties for all active addons
    for addon in all_addons:
        properties[addon["data_name"]] = {
            "type": "integer",
            "description": f"Qty for the {addon['name']} add-on"
        }
    return properties


def get_retell_tools(business):
    api_credential = ApiCredential.objects.filter(business=business).first()
    secret_key = api_credential.secretKey
    all_addons = get_all_active_addons(business)

    # Base required fields for booking tool
    required_fields = [
        "first_name", "last_name", "email", "phone_number", "address", "city", 
        "state", "zip_code", "bedrooms", "bathrooms", "area", "service_type", 
        "appointment_date_time", "business_id"
    ]
    
    # Add dynamic addon data names to the required list
    for addon in all_addons:
        required_fields.append(addon["data_name"])

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
            "url": f"https://cleaningbizai.com/api/availability/{secret_key}/",
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
                "properties": get_book_appointment_tool_properties(business),
                "required": required_fields
            }
        },
        {
            "type": "custom",
            "name": "reschedule_booking",
            "description": "This is to reschedule booking to future date and time",
            "url": "https://cleaningbizai.com/api/reschedule-booking/",
            "execution_message_description": "Reschedudling Appointment",
            "timeout_ms": 10000,
            "speak_during_execution": True,
            "speak_after_execution": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {
                        "type": "string",
                        "description": "The booking id"
                    },
                    "next_date_time": {
                        "type": "string",
                        "description": "Futrue date time for Rescheduling in Human readable format"
                    }
                },
                "required": [
                    "booking_id",
                    "next_date_time"
                ]
            }
        },
        {
            "type": "custom",
            "name": "cancel_booking",
            "description": "This is used to cancel booking which requires booking id to proceed.",
            "url": "https://cleaningbizai.com/api/cancel_booking/",
            "execution_message_description": "Cancelling Appointment",
            "timeout_ms": 10000,
            "speak_during_execution": True,
            "speak_after_execution": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {
                        "type": "string",
                        "description": "The booking id"
                    }
                },
                "required": [
                    "booking_id",
                ]
            }
        },
    ]
    return custom_tools