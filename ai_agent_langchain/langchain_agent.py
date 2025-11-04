"""
LangChain Agent Implementation for SMS-based AI Assistant
This module implements a LangChain-based conversational agent that handles
SMS conversations through Twilio for appointment booking and management.
"""

from typing import List, Dict, Any, Optional
import os
import json
from datetime import datetime
import functools
import inspect

from langchain.agents import AgentExecutor
from langchain.agents.openai_functions_agent.base import OpenAIFunctionsAgent
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from langchain.prompts import MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain_community.chat_models import ChatOpenAI

from django.conf import settings
from django.utils import timezone

from business.models import Business, ServiceOffering, ServiceItem
from .models import Chat, Message, AgentConfig
from .agent_tools.tools import CheckAvailabilityTool, BookAppointmentTool, RescheduleAppointmentTool, CancelAppointmentTool, GetServiceItemsTool

class LangChainAgent:
    """
    LangChain-based conversational agent for handling SMS interactions.
    This agent uses OpenAI's function calling capabilities to execute tools
    for appointment booking, rescheduling, cancellation, and availability checking.
    """
    
    def __init__(self, business_id: str, chat_id: Optional[str] = None, 
                 phone_number: Optional[str] = None, session_key: Optional[str] = None):
        """
        Initialize the LangChain agent with business and chat information.
        
        Args:
            business_id: The ID of the business this agent is representing
            chat_id: Optional ID of an existing chat to continue
            phone_number: Optional phone number for the chat
            session_key: Optional session key for web-based chats
        """
        self.business_id = business_id
        self.chat_id = chat_id
        self.phone_number = phone_number
        self.session_key = session_key
        
        # Load business information
        try:
            self.business = Business.objects.get(id=business_id)
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
        if self.chat_id:
            try:
                return Chat.objects.get(id=self.chat_id, business=self.business)
            except Chat.DoesNotExist:
                raise ValueError(f"Chat with ID {self.chat_id} not found for business {self.business.name}")
        
        # Try to find an existing chat first
        chat_kwargs = {
            'business': self.business,
        }
        
        if self.phone_number:
            chat_kwargs['phone_number'] = self.phone_number
        
        if self.session_key:
            chat_kwargs['session_key'] = self.session_key
        
        # Try to get an existing chat first
        existing_chat = Chat.objects.filter(**chat_kwargs).first()
        if existing_chat:
            # Update the is_active flag if needed
            if not existing_chat.is_active:
                existing_chat.is_active = True
                existing_chat.save(update_fields=['is_active', 'updated_at'])
            return existing_chat
        
        # Create a new chat if none exists
        return Chat.objects.create(**chat_kwargs)
    
    def _initialize_llm(self) -> ChatOpenAI:
        """Initialize the LLM with appropriate settings."""
        api_key = settings.OPENAI_API_KEY
        model_name = getattr(settings, 'OPENAI_MODEL_NAME', 'gpt-4-0125-preview')
        
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
        messages = self.chat.messages.all().order_by('created_at')
        
        for msg in messages:
            if msg.role == 'user':
                memory.chat_memory.add_user_message(msg.content)
            elif msg.role == 'assistant':
                memory.chat_memory.add_ai_message(msg.content)
            elif msg.role == 'system':
                # System messages are handled separately in the agent initialization
                pass
        
        return memory
    
    def _initialize_tools(self) -> List:
        """Initialize the tools for the agent."""
        print(f"[DEBUG] Initializing tools for business: {self.business.name} (ID: {self.business.id})")
        
        # Create the tools
        check_availability_tool = CheckAvailabilityTool()
        book_appointment_tool = BookAppointmentTool()
        reschedule_appointment_tool = RescheduleAppointmentTool()
        cancel_appointment_tool = CancelAppointmentTool()
        get_service_items_tool = GetServiceItemsTool()
        
        # Add business_id to the tools that need it
        def wrap_tool_run(tool, original_run):
            """Wrap the tool's _run method to add business_id if not provided."""
            @functools.wraps(original_run)
            def wrapped_run(*args, **kwargs):
                print(f"[DEBUG] Running {tool.name} with args: {args}, kwargs: {kwargs}")
                
                # Only add business_id if the tool accepts it
                if 'business_id' in inspect.signature(original_run).parameters:
                    if 'business_id' not in kwargs or not kwargs['business_id']:
                        kwargs['business_id'] = str(self.business.id)
                        print(f"[DEBUG] Added business_id: {kwargs['business_id']}")
                
                # Filter out kwargs that aren't accepted by the function
                valid_params = inspect.signature(original_run).parameters.keys()
                filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
                
                if filtered_kwargs != kwargs:
                    print(f"[DEBUG] Filtered kwargs: {kwargs} -> {filtered_kwargs}")
                
                return original_run(*args, **filtered_kwargs)
            return wrapped_run
        
        # Wrap each tool's _run method
        for tool in [check_availability_tool, book_appointment_tool, reschedule_appointment_tool, cancel_appointment_tool, get_service_items_tool]:
            original_run = tool._run
            tool._run = wrap_tool_run(tool, original_run)
            print(f"[DEBUG] Wrapped {tool.name}._run method")
        
        print(f"[DEBUG] Created tools: {check_availability_tool.name}, {book_appointment_tool.name}, {reschedule_appointment_tool.name}, {cancel_appointment_tool.name}, {get_service_items_tool.name}")
        
        return [
            check_availability_tool,
            book_appointment_tool,
            reschedule_appointment_tool,
            cancel_appointment_tool,
            get_service_items_tool
        ]

    def _get_system_prompt(self) -> str:
        """
        Generate a dynamic system prompt based on business details.
        This customizes the agent's behavior for each business.
        """
        # Get agent config from database or use default
        agent_config = AgentConfig.objects.filter(business=self.business, is_active=True).first()
        
        # Get current date and time
        current_date = timezone.now().strftime("%Y-%m-%d")
        current_time = timezone.now().strftime("%H:%M")
        
        if agent_config and agent_config.prompt:
            # Use custom prompt from database
            system_prompt = agent_config.prompt
        else:
            # Generate default prompt
            business_name = self.business.name
            business_description = self.business.description or ""
            business_id = str(self.business.id)  # Convert UUID to string
            
            # Get services with their linked service items
            services = ServiceOffering.objects.filter(business=self.business, is_active=True).prefetch_related('service_items')
            
            services_text = ""
            for service in services:
                services_text += f"\n{service.name} - ${service.price} ({service.duration} minutes):\n"
                services_text += f"  Description: {service.description or 'No description'}\n"
                
                # Get service items linked to this service
                service_items = service.service_items.filter(is_active=True)
                if service_items.exists():
                    services_text += f"  Customization Options:\n"
                    for item in service_items:
                        # Build item description with price and duration
                        item_desc = f"    • {item.name} (identifier: {item.identifier})"
                        
                        # Add pricing information based on field type
                        if item.field_type == 'boolean' and item.option_pricing:
                            services_text += f"{item_desc}\n"
                            services_text += f"      Type: Yes/No question\n"
                            services_text += f"      Options:\n"
                            for option, config in item.option_pricing.items():
                                price_type = config.get('price_type', 'free')
                                duration_info = f", +{item.duration_minutes} min" if item.duration_minutes > 0 else ""
                                if price_type == 'paid':
                                    services_text += f"        - {option.capitalize()}: ${config.get('price_value', 0)}{duration_info}\n"
                                else:
                                    services_text += f"        - {option.capitalize()}: Free{duration_info}\n"
                        elif item.field_type == 'select' and item.option_pricing:
                            services_text += f"{item_desc}\n"
                            services_text += f"      Type: Choose one option\n"
                            services_text += f"      Options:\n"
                            for option, config in item.option_pricing.items():
                                price_type = config.get('price_type', 'free')
                                duration_info = f", +{item.duration_minutes} min" if item.duration_minutes > 0 else ""
                                if price_type == 'paid':
                                    services_text += f"        - {option}: ${config.get('price_value', 0)}{duration_info}\n"
                                else:
                                    services_text += f"        - {option}: Free{duration_info}\n"
                        elif item.field_type == 'number':
                            duration_info = f", +{item.duration_minutes} min each" if item.duration_minutes > 0 else ""
                            if item.price_type == 'paid':
                                services_text += f"{item_desc} - ${item.price_value} per unit{duration_info}\n"
                            else:
                                services_text += f"{item_desc} - Free{duration_info}\n"
                            services_text += f"      Type: Enter quantity\n"
                        else:  # text, textarea
                            duration_info = f", +{item.duration_minutes} min" if item.duration_minutes > 0 else ""
                            if item.price_type == 'paid':
                                services_text += f"{item_desc} - ${item.price_value}{duration_info}\n"
                            else:
                                services_text += f"{item_desc} - Free{duration_info}\n"
                            services_text += f"      Type: Text input\n"
                        
                        services_text += f"      {'Required' if not item.is_optional else 'Optional'}\n"
                services_text += "\n"
            
            # Default system prompt
            system_prompt = f"""You are a friendly booking assistant for {business_name}. 
{business_description}

Today's date is {current_date} and the current time is {current_time}.

AVAILABLE SERVICES:
{services_text}

YOUR CONVERSATION STYLE:
- Write naturally like you're texting a friend
- Use simple, casual language
- NO markdown formatting (no **, no ##, no bullets)
- NO numbered lists in your responses
- Ask ONE question at a time
- Keep messages short and conversational
- Use natural transitions like "Great!", "Perfect!", "Got it!"

CONVERSATION FLOW:
1. Greet warmly and ask if they want to book a service
2. Once they choose a service, ask for customization details ONE AT A TIME
3. After each answer, acknowledge it and move to the next question
4. Calculate running total as you go and mention it naturally
5. Ask for their preferred date and time
6. Collect their name, phone, and email
7. Summarize everything and confirm before booking
8. IMPORTANT: Actually call the book_appointment tool (don't just say it's booked)

HOW TO PRESENT SERVICES:
- When customer asks about services, mention the price and duration
- Example: "We offer Standard Cleaning for $100, takes about 120 minutes."
- If they choose a service, mention if there are customization options available

HOW TO ASK FOR SERVICE ITEMS:
- Ask for ONE item at a time, not all at once
- ALWAYS mention the price when asking about an option
- Use natural questions like:
  * "How many bedrooms would you like cleaned? It's $10 per bedroom."
  * "Would you like us to clean the driveway too? That's an extra $20."
  * "Which cleaner product would you prefer - best cleaner ($10) or better cleaner ($5)?"
- After they answer, acknowledge and move to next item
- Keep track of pricing and mention running totals naturally

EXAMPLE GOOD CONVERSATION:
Customer: I want cleaning service
You: Great! I can help you book our Standard Cleaning service. How many bedrooms would you like us to clean?
Customer: 3 bedrooms
You: Perfect! That's 3 bedrooms at $10 each, so $30 added to the base price of $100. Would you also like the driveway cleaned?
Customer: No thanks
You: Got it, no driveway cleaning. Last question - which cleaner product would you prefer, the best cleaner or better cleaner?

FORMATTING RULES (ALWAYS FOLLOW):
- NEVER EVER use ** for bold (not even in confirmations)
- NEVER use numbered lists like "1.", "2.", "3."
- NEVER use bullet points like "- " or "* "
- Write naturally in plain text only
- Use line breaks for readability, not formatting
- This applies to ALL messages including booking confirmations

TECHNICAL DETAILS:
- Convert dates to YYYY-MM-DD format internally
- Convert times to HH:MM 24-hour format internally
- Use exact identifiers from service items list
- business_id is automatically provided

SERVICE ITEMS FORMAT FOR TOOL CALLS:
[
  {{"identifier": "item_id", "value": "user_response", "quantity": 1}}
]

TOOLS YOU MUST USE:
- check_availability: Check if time slot is free
- book_appointment: MUST call this to actually create the booking (required: date, time, service_name, customer_name, customer_phone, customer_email, service_items)
- reschedule_appointment: Change existing booking
- cancel_appointment: Cancel booking
- get_service_items: Get more details if needed

CRITICAL RULES:
1. When customer confirms, you MUST call book_appointment tool. Just saying "booked" doesn't create it in the system.
2. After booking is created, you will receive booking details including Booking ID. ALWAYS share the Booking ID with the customer.
3. NEVER use ** or any markdown in your confirmation message.
4. Remember all bookings you create in the conversation - if customer asks for booking ID later, provide it from context.

BOOKING CONFIRMATION FORMAT:
When you receive BOOKING_CONFIRMED from the tool, respond naturally like:
"All set! Your appointment is confirmed for [date] at [time]. Your booking ID is [ID]. You'll receive a confirmation email at [email]. Total is $[amount] for [duration] minutes."

Be warm, helpful, and conversational. Guide them smoothly through the booking process.
"""
        
        return system_prompt
    
    def _initialize_agent(self) -> OpenAIFunctionsAgent:
        """Initialize the OpenAI Functions agent."""
        print(f"[DEBUG] Initializing agent for business: {self.business.name} (ID: {self.business.id})")
        
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
        Message.objects.create(
            chat=self.chat,
            role='user',
            content=user_message,
            created_at=timezone.now()
        )
        
        try:
            # Process with LangChain agent
            response = self.agent_executor.run(user_message)
            
            print(f"[DEBUG] Agent response: {response}")
            
            # Save assistant response to database
            Message.objects.create(
                chat=self.chat,
                role='assistant',
                content=response,
                created_at=timezone.now()
            )
            
            return response
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            print(f"[DEBUG] Error running agent: {str(e)}")
            print(f"[DEBUG] Traceback: {error_traceback}")
            
            # Save error as system message
            Message.objects.create(
                chat=self.chat,
                role='system',
                content=f"Error processing message: {str(e)}",
                created_at=timezone.now()
            )
            
            # Return a user-friendly error message
            return "I'm sorry, I encountered an error processing your request. Please try again later."
    
    def update_chat_summary(self, booking_id: Optional[str] = None) -> None:
        """
        Update the chat summary with key information extracted from the conversation.
        This is useful for analytics and quick reference.
        """
        # Get all messages in this chat
        messages = self.chat.messages.all().order_by('created_at')
        
        if not messages:
            return
        
        # Extract basic summary info
        message_count = messages.count()
        first_message_time = messages.first().created_at
        last_message_time = messages.last().created_at
        
        # Create a simple summary
        summary = {
            'message_count': message_count,
            'first_message': first_message_time.isoformat(),
            'last_message': last_message_time.isoformat(),
            'duration_seconds': (last_message_time - first_message_time).total_seconds(),
            'booking_id': booking_id or '',
        }
        
        # Update the chat summary
        self.chat.summary = summary
        self.chat.save(update_fields=['summary', 'updated_at'])
