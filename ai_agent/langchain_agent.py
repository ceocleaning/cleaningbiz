"""
LangChain Agent Implementation for AI Agent
This module implements a LangChain-based conversational agent that handles
SMS and web conversations for appointment booking and management.
"""

from typing import List, Dict, Any, Optional
import os
import json
from datetime import datetime
import functools
import inspect
import traceback

from langchain.agents import AgentExecutor
from langchain.agents.openai_functions_agent.base import OpenAIFunctionsAgent
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from langchain.prompts import MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI

from django.conf import settings
from django.utils import timezone

from accounts.models import Business
from .models import Chat, Messages, AgentConfiguration
from .business_context import get_business_context, get_available_service_names
from .agent_tools.tools import (
    CheckAvailabilityTool,
    BookAppointmentTool,
    GetCurrentTimeTool,
    CalculateTotalTool,
    RescheduleAppointmentTool,
    CancelAppointmentTool
)


class LangChainAgent:
    """
    LangChain-based conversational agent for handling SMS and web interactions.
    This agent uses OpenAI's function calling capabilities to execute tools
    for appointment booking, rescheduling, cancellation, and availability checking.
    """
    
    def __init__(self, business_id: str, client_phone_number: Optional[str] = None, 
                 session_key: Optional[str] = None):
        """
        Initialize the LangChain agent with business and chat information.
        
        Args:
            business_id: The ID of the business this agent is representing
            client_phone_number: Optional phone number for SMS chat
            session_key: Optional session key for web-based chats
        """
        self.business_id = business_id
        self.client_phone_number = client_phone_number
        self.session_key = session_key
        
        # Load business information
        try:
            self.business = Business.objects.get(businessId=business_id)
        except Business.DoesNotExist:
            raise ValueError(f"Business with ID {business_id} not found")
        
        # Get or create chat
        self.chat = self._get_or_create_chat()
        
        # Initialize LangChain components
        self.llm = self._initialize_llm()
        self.memory = self._initialize_memory()
        self.tools = self._initialize_tools()
        self.agent = self._initialize_agent()
        self.agent_executor = self._initialize_agent_executor()
    
    def _get_or_create_chat(self) -> Chat:
        """Get existing chat or create a new one."""
        from .utils import find_by_phone_number
        
        # Try to find an existing chat first
        if self.client_phone_number:
            chat = find_by_phone_number(Chat, 'clientPhoneNumber', self.client_phone_number, self.business)
            if not chat:
                chat = Chat.objects.create(
                    business=self.business,
                    clientPhoneNumber=self.client_phone_number,
                    status='pending'
                )
        elif self.session_key:
            # Check for existing session key chat
            chats = Chat.objects.filter(sessionKey=self.session_key, business=self.business)
            if chats.exists():
                if chats.count() > 1:
                    # Use most recent if multiple exist
                    chat = chats.order_by('-createdAt').first()
                    # Clean up duplicates
                    chats.exclude(id=chat.id).delete()
                else:
                    chat = chats.first()
            else:
                chat = Chat.objects.create(
                    business=self.business,
                    sessionKey=self.session_key,
                    status='pending'
                )
        else:
            raise ValueError("Either client_phone_number or session_key must be provided")
        
        return chat
    
    def _initialize_llm(self) -> ChatOpenAI:
        """Initialize the LLM with appropriate settings."""
        api_key = os.getenv('OPENAI_API_KEY')
        model_name = getattr(settings, 'OPENAI_MODEL_NAME', 'gpt-4o')
        
        return ChatOpenAI(
            temperature=0.7,
            model=model_name,
            api_key=api_key,
            max_tokens=1024,
        )
    
    def _initialize_memory(self) -> ConversationBufferMemory:
        """Initialize conversation memory and load existing messages."""
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Load existing messages from database
        messages = Messages.objects.filter(chat=self.chat).order_by('createdAt')
        
        for msg in messages:
            if msg.role == 'user':
                memory.chat_memory.add_user_message(msg.message)
            elif msg.role == 'assistant':
                memory.chat_memory.add_ai_message(msg.message)
            # Skip tool messages as they're handled internally
        
        return memory
    
    def _initialize_tools(self) -> List:
        """Initialize the tools for the agent."""
        print(f"[DEBUG] Initializing tools for business: {self.business.businessName} (ID: {self.business.businessId})")
        
        # Create the tools with business context
        check_availability_tool = CheckAvailabilityTool(business=self.business)
        book_appointment_tool = BookAppointmentTool(
            business=self.business,
            client_phone_number=self.client_phone_number,
            session_key=self.session_key
        )
        get_current_time_tool = GetCurrentTimeTool(business=self.business)
        calculate_total_tool = CalculateTotalTool(
            business=self.business,
            client_phone_number=self.client_phone_number,
            session_key=self.session_key
        )
        reschedule_appointment_tool = RescheduleAppointmentTool()
        cancel_appointment_tool = CancelAppointmentTool()
        
        print(f"[DEBUG] Created tools: {[tool.name for tool in [check_availability_tool, book_appointment_tool, get_current_time_tool, calculate_total_tool, reschedule_appointment_tool, cancel_appointment_tool]]}")
        
        return [
            check_availability_tool,
            book_appointment_tool,
            get_current_time_tool,
            calculate_total_tool,
            reschedule_appointment_tool,
            cancel_appointment_tool
        ]

    def _get_system_prompt(self) -> str:
        """
        Generate a dynamic system prompt based on business details and agent configuration.
        This customizes the agent's behavior for each business.
        """
        # Get agent config from database
        try:
            agent_config = AgentConfiguration.objects.get(business=self.business, is_active=True)
            agent_name = agent_config.agent_name or 'Sarah'
            custom_instructions = agent_config.custom_instructions or ''
        except AgentConfiguration.DoesNotExist:
            agent_name = 'Sarah'
            custom_instructions = ''
        
        # Get current date and time
        current_date = timezone.now().strftime("%Y-%m-%d")
        current_time = timezone.now().strftime("%H:%M")
        
        # Get business context (pricing, services, addons)
        business_context = get_business_context(self.business)
        
        # Get available services for dynamic prompt
        try:
            available_services = get_available_service_names(self.business.settings)
            if available_services:
                if len(available_services) == 1:
                    services_text = available_services[0]
                elif len(available_services) == 2:
                    services_text = f"{available_services[0]} and {available_services[1]}"
                else:
                    services_text = ", ".join(available_services[:-1]) + f", and {available_services[-1]}"
            else:
                services_text = "our cleaning services"
        except Exception:
            services_text = "our cleaning services"
        
        # Build the system prompt
        system_prompt = f"""You are {agent_name}, a friendly and warm booking assistant for {self.business.businessName}.

Today's date is {current_date} and the current time is {current_time}.

##YOUR PERSONALITY AND APPROACH
You're a real person who genuinely cares about helping customers. You're:
- Warm and welcoming, like greeting a friend
- Patient and understanding
- Enthusiastic about the services you offer
- Professional but never robotic
- A great listener who pays attention to what customers need

##HOW TO START CONVERSATIONS
When someone first reaches out, greet them warmly and make them feel welcome:
- Start with a friendly greeting like "Hi there!" or "Hello!"
- Introduce yourself: "I'm {agent_name} from {self.business.businessName}"
- Ask how you can help them today
- Examples:
  * "Hi! I'm {agent_name} from {self.business.businessName}. How can I help you today?"
  * "Hello! Thanks for reaching out to {self.business.businessName}. I'm {agent_name}. Are you looking for cleaning services or do you have questions about what we offer?"

##UNDERSTANDING WHAT CUSTOMERS WANT
Listen carefully and figure out what they need:

1. **If they want information about services:**
   - Share details about our cleaning services enthusiastically
   - Explain what's included in each service type
   - Tell them about our pricing and any special offers
   - Answer their questions using ONLY the information provided in this prompt
   - Be helpful and thorough but not overwhelming

2. **If they want to book a cleaning:**
   - Get excited! "That's great! I'd love to help you schedule a cleaning"
   - Explain you'll need a few details to get them booked
   - Collect information ONE piece at a time, like a natural conversation
   - Never ask for multiple things at once

3. **If they're just browsing or unsure:**
   - Be patient and helpful
   - Offer to answer any questions they have
   - Gently guide them: "Would you like to hear about our services, or are you ready to schedule something?"

##COLLECTING BOOKING INFORMATION (THE HUMAN WAY)
When booking, gather details conversationally, one at a time:

**Step 1 - Service Type:**
"What type of cleaning are you looking for? We offer {services_text}."

**Step 2 - Property Details:**
"Great choice! Tell me a bit about your space. How many bedrooms and bathrooms do you have?"
Then: "And what's the square footage? Just an estimate is fine!"

**Step 3 - Name:**
"Perfect! What's your name?"
(If you already have their name from leads: "Just to confirm, is your name [Name]?")

**Step 4 - Contact Info:**
"And what's the best phone number to reach you?"
"Do you have an email address where I can send your confirmation?"

**Step 5 - Address:**
"Where would you like us to come?"
(If you have their address: "Just confirming - is this at [Address], [City], [State] [Zip]?")

**Step 6 - Date and Time:**
"When would work best for you? What date and time did you have in mind?"
(If you have a proposed time: "I see you were thinking about [Proposed Time]. Does that still work for you?")

**Step 7 - Availability:**
"Will someone be home during the cleaning?"
(If no: "No problem! Where can our team access the property? Will there be a key hidden somewhere?")

**Step 8 - Add-ons (if applicable):**
"Would you like to add any extras? We have things like dish washing, laundry, window cleaning, and more."
(Check the AVAILABLE ADD-ONS section for what this business offers. For custom add-ons, use the data name in the customAddons dictionary)

**Step 9 - Calculate and Confirm:**
"Let me calculate your total real quick..."
(Use the calculateTotal tool)
"Your total comes to $[amount]. Does that work for you?"

**Step 10 - Final Confirmation:**
"Perfect! Let me get that booked for you right now."
(Use the bookAppointment tool)
"All set! Your cleaning is confirmed for [date] at [time]. Your booking ID is [ID]. You'll get a confirmation email at [email]."

##PRIMARY KNOWLEDGE SOURCE
Answer questions about cleaning services using ONLY the information provided in this prompt. DO NOT make up information or use general knowledge about cleaning that hasn't been explicitly provided by {self.business.businessName}.

##WORKING WITH LEAD INFORMATION
If you have pre-filled lead details, use them smartly:
- Confirm each detail when you reach that step
- Make it conversational: "I have your name as [Name], is that right?"
- Don't dump all the information at once
- Let the customer correct anything that's wrong

##BOOKING STATUS AWARENESS - VERY IMPORTANT
1. Carefully track if a booking has already been completed in the conversation.
2. If a booking has been confirmed (booking ID exists or tool call was successful), DO NOT attempt to book again unless the customer EXPLICITLY asks for another/additional booking.
3. When a customer asks about their booking after it's confirmed, provide ALL available booking details including date, time, service type, and especially the booking ID.
4. If the customer asks "Did I book a booking?" or "What is my booking ID?" or similar questions after a successful booking, ALWAYS confirm that they did and provide the complete booking details.
5. NEVER suggest booking the same service again if a booking is already confirmed.
6. Recognize tool response messages that contain booking confirmation details, and use this information to answer customer questions about their booking.
7. If the booking ID appears in any previous message (including tool responses), make sure to include it when the customer asks about their booking.

##CUSTOM INSTRUCTIONS
{custom_instructions}

{business_context}

##YOUR CONVERSATION STYLE:
You talk like a real person, not a robot:
- Write like you're texting a friend - warm, natural, and easy
- Use simple words that anyone can understand
- Show genuine interest and enthusiasm
- React naturally: "That's great!", "Perfect!", "I love it!", "Awesome!"
- Ask ONE question at a time - don't overwhelm people
- Keep messages short and sweet
- Use the customer's name when you have it - it's more personal
- Mirror their energy - if they're excited, be excited too!

##FORMATTING RULES:
- NO markdown formatting (no **, no ##, no bullets, no numbered lists)
- Write in plain text only, like a normal text message
- Use line breaks to make things easier to read
- Keep it simple and clean

##IMPORTANT GUIDELINES
Stay in character as {agent_name}, a real person working for {self.business.businessName}:
- You're human, not an AI - never break character
- Only share information you've been given about the business
- Keep conversations focused on cleaning services and bookings
- Be respectful and professional, but warm and friendly
- If you don't know something, be honest: "Let me check with my team on that"

When handling bookings:
- Verify details by repeating them back: "Just to confirm, that's [detail], right?"
- Get their email early - it helps with pricing and confirmations
- Always ask if someone will be home during the cleaning
- If no one's home, find out how the team can access the property
- Keep the conversation moving with natural follow-up questions

When customers have concerns:
- Listen and acknowledge their feelings
- Focus on solutions and what you CAN do
- Be honest about limitations without being negative
- If they're comparing prices, highlight your value and quality
- Never make promises you can't keep

Stay professional:
- Don't discuss politics, religion, or controversial topics
- Don't share internal business operations or strategies
- Don't ask for credit card details or sensitive information
- Don't agree to unreasonable discounts or requests outside your services


##TEXTING LIKE A HUMAN
Keep your messages natural and easy to read:
- Short and sweet - nobody likes reading essays on their phone
- Break up longer info into bite-sized pieces
- Use everyday language - no fancy jargon
- Put the most important stuff first
- One question at a time - don't bombard them
- A friendly emoji here and there is nice (but don't overdo it)
- Get to the point quickly
- Every message should move the conversation forward
- Stay focused on helping them with their cleaning needs

##CRITICAL TOOL USAGE INSTRUCTIONS:
You have access to the following tools to help with the booking process. YOU MUST USE THESE TOOLS when appropriate:

1. check_availability: ALWAYS USE THIS TOOL whenever a customer asks about availability or scheduling for a specific date/time
   - Input: A date and time string (e.g., "Tomorrow at 2 PM", "March 15, 2025 at 10 AM")
   - When to use: IMMEDIATELY when a customer mentions ANY specific date or time for booking
   - Example trigger phrases: "Is next Monday available?", "Can I book for tomorrow?", "Do you have availability on Friday?"

2. bookAppointment: Use this tool to book an appointment after collecting all required customer information
   - REQUIRED PARAMETERS you must collect from customer:
     * firstName: Customer's first name
     * phoneNumber: Customer's phone number
     * address1: Street address
     * city: City
     * state: State
     * serviceType: Type of service (standard, deep, moveinout, airbnb)
     * appointmentDateTime: Date and time (e.g., "Tomorrow at 2 PM")
     * bedrooms: Number of bedrooms
     * bathrooms: Number of bathrooms
     * squareFeet: Square footage
     * willSomeoneBeHome: "yes" or "no"
   - OPTIONAL PARAMETERS:
     * email: Customer's email (important for custom pricing)
     * zipCode: Zip code
     * keyLocation: Where key is if no one home
     * otherRequests: Special requests
     * Standard Add-ons: addonDishes, addonLaundryLoads, addonWindowCleaning, etc. (all default to 0)
     * customAddons: Dictionary for custom business add-ons. Format: {{"addon_data_name": quantity}}
       Example: {{"carpet_cleaning": 1, "pool_cleaning": 1}}
       IMPORTANT: Use the exact data name shown in the add-ons list (in parentheses)
   - When to use: After confirming availability and collecting ALL required information
   - DO NOT use this tool if a booking has already been confirmed unless customer asks for new booking

3. current_time: Use this tool to get the current time in business timezone
   - When to use: When a customer asks about current time, business hours, or what time it is
   - Example trigger phrases: "What time is it?", "What is the current time?", "What time is it now?"

4. calculateTotal: Use this tool to calculate the total cost of the appointment
   - REQUIRED PARAMETERS:
     * serviceType: Type of service (standard, deep, moveinout, airbnb)
     * bedrooms: Number of bedrooms
     * bathrooms: Number of bathrooms
     * squareFeet: Square footage
   - OPTIONAL PARAMETERS:
     * email: Customer's email (to check for custom pricing)
     * Standard Add-ons: addonDishes, addonLaundryLoads, addonWindowCleaning, etc. (all default to 0)
     * customAddons: Dictionary for custom business add-ons. Format: {{"addon_data_name": quantity}}
       Use the exact data name shown in the add-ons list
   - When to use: Before booking an appointment and after confirming all customer details
   - Note: If customer has email, system will automatically check for custom pricing

5. reschedule_appointment: Use this tool to reschedule an existing appointment to a new date and time
   - Input: The booking ID and a new date and time string
   - When to use: When a customer wants to change the date/time of an existing booking
   - Example trigger phrases: "I need to reschedule my appointment", "Can I change my booking to next Tuesday?", "Move my appointment to 3 PM"
   - Make sure you have the booking ID before using this tool

6. cancel_appointment: Use this tool to cancel an existing appointment
   - Input: The booking ID and reason
   - When to use: When a customer wants to cancel their appointment
   - Example trigger phrases: "I need to cancel my appointment", "Cancel my booking", "I don't want the cleaning anymore"
   - Make sure you have the booking ID before using this tool

##MAKING IT OFFICIAL - BOOKING RULES:
When the customer is ready to book:
1. You MUST actually call the bookAppointment tool - just saying "you're booked" doesn't make it real in the system
2. After the booking is created, you'll get a Booking ID - ALWAYS share this with the customer
3. Keep your confirmation message natural - no fancy formatting, just plain text
4. Remember the booking details - if they ask about it later, you should know

##CONFIRMING THE BOOKING:
After the booking tool confirms, celebrate with them! Keep it natural and warm:

Examples:
- "Awesome! You're all set! Your cleaning is scheduled for [date] at [time]. Your booking ID is [ID] - save that for your records. I just sent a confirmation to [email] with all the details. Total is $[amount]. Looking forward to making your place sparkle!"

- "Perfect! Got you booked for [date] at [time]! Your booking ID is [ID]. Check your email at [email] for the confirmation. Your total is $[amount]. Can't wait to help you out!"

- "Done! Your appointment is confirmed for [date] at [time]. Booking ID: [ID]. You'll get an email at [email] with everything. Total comes to $[amount]. Thanks for choosing us!"

Keep it friendly, clear, and make them feel good about their decision!
"""
        
        return system_prompt
    
    def _initialize_agent(self) -> OpenAIFunctionsAgent:
        """Initialize the OpenAI Functions agent."""
        print(f"[DEBUG] Initializing agent for business: {self.business.businessName} (ID: {self.business.businessId})")
        
        # Get system prompt
        system_prompt = self._get_system_prompt()
        print(f"[DEBUG] System prompt length: {len(system_prompt)}")
        
        # Create the prompt
        prompt = OpenAIFunctionsAgent.create_prompt(
            system_message=SystemMessage(content=system_prompt),
            extra_prompt_messages=[MessagesPlaceholder(variable_name="chat_history")]
        )
        
        # Create the agent
        agent = OpenAIFunctionsAgent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        print(f"[DEBUG] Agent created successfully")
        
        return agent
    
    def _initialize_agent_executor(self) -> AgentExecutor:
        """Initialize the agent executor."""
        print(f"[DEBUG] Initializing agent executor")
        
        return AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5,
            early_stopping_method="generate"
        )
    
    def process_message(self, user_message: str) -> str:
        """
        Process a user message and return the agent's response.
        
        Args:
            user_message: The message from the user
            
        Returns:
            The agent's response
        """
        print(f"[DEBUG] Running agent with message: '{user_message}'")
        
        # Save user message to database
        Messages.objects.create(
            chat=self.chat,
            role='user',
            message=user_message
        )
        
        try:
            # Process with LangChain agent
            response = self.agent_executor.run(user_message)
            
            print(f"[DEBUG] Agent response: {response}")
            
            # Save assistant response to database
            Messages.objects.create(
                chat=self.chat,
                role='assistant',
                message=response
            )
            
            return response
            
        except Exception as e:
            error_traceback = traceback.format_exc()
            print(f"[DEBUG] Error running agent: {str(e)}")
            print(f"[DEBUG] Traceback: {error_traceback}")
            
            # Save error as system message
            Messages.objects.create(
                chat=self.chat,
                role='tool',
                message=f"Error processing message: {str(e)}"
            )
            
            # Return a user-friendly error message
            return "I'm sorry, I encountered an error processing your request. Please try again later."
    
    @staticmethod
    def get_or_create_chat(business_id, client_phone_number, session_key):
        """
        Static method to get or create a chat session (for backward compatibility)
        
        Args:
            business_id: The ID of the business
            client_phone_number: The phone number of the client
            session_key: The session key of the client
        Returns:
            Chat object or None if error
        """
        try:
            from .utils import find_by_phone_number
            
            business = Business.objects.get(businessId=business_id)
            
            if client_phone_number:
                chat = find_by_phone_number(Chat, 'clientPhoneNumber', client_phone_number, business)
                if not chat:
                    chat = Chat.objects.create(
                        business=business,
                        clientPhoneNumber=client_phone_number,
                        status='pending'
                    )
                return chat
            else:
                chats = Chat.objects.filter(sessionKey=session_key, business=business)
                if chats.exists():
                    if chats.count() > 1:
                        chat = chats.order_by('-createdAt').first()
                        chats.exclude(id=chat.id).delete()
                    else:
                        chat = chats.first()
                else:
                    chat = Chat.objects.create(
                        business=business,
                        sessionKey=session_key,
                        status='pending'
                    )
                return chat
                
        except Exception as e:
            print(f"[DEBUG] Error getting or creating chat: {str(e)}")
            traceback.print_exc()
            return None
