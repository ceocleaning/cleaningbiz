from langchain.tools import BaseTool
from pydantic import BaseModel, PrivateAttr
from typing import Optional, Type, Any
import json
from decimal import Decimal

from .inputs import (
    CheckAvailabilityInput, 
    BookAppointmentInput, 
    GetCurrentTimeInput,
    CalculateTotalInput,
    RescheduleAppointmentInput,
    CancelAppointmentInput
)

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        from django.db import models
        
        if isinstance(o, Decimal):
            return str(o)
        elif isinstance(o, models.Model):
            # Skip Django model instances - they should not be in JSON responses
            return None
        return super(DecimalEncoder, self).default(o)
    
    def encode(self, o):
        """Override encode to filter out model instances from dicts and lists"""
        from django.db import models
        
        def filter_models(obj):
            if isinstance(obj, dict):
                return {k: filter_models(v) for k, v in obj.items() if not isinstance(v, models.Model)}
            elif isinstance(obj, list):
                return [filter_models(item) for item in obj if not isinstance(item, models.Model)]
            elif isinstance(obj, models.Model):
                return None
            return obj
        
        filtered = filter_models(o)
        return super(DecimalEncoder, self).encode(filtered)


class CheckAvailabilityTool(BaseTool):
    """Tool for checking appointment availability"""
    name: str = "check_availability"
    description: str = """Check if a specific date and time is available for booking.
    Use this tool whenever a customer asks about availability or scheduling for a specific date/time.
    Input should be a natural language date/time string like 'Tomorrow at 2 PM' or 'March 15, 2025 at 10 AM'."""
    args_schema: Type[BaseModel] = CheckAvailabilityInput
    
    _business: Any = PrivateAttr()
    
    def __init__(self, business=None, **kwargs):
        super().__init__(**kwargs)
        self._business = business
    
    def _run(self, date: str) -> str:
        """Check availability for a given date/time"""
        from ..api_views import check_availability
        
        try:
            result = check_availability(self._business, date)
            return json.dumps(result, cls=DecimalEncoder)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, cls=DecimalEncoder)


class BookAppointmentTool(BaseTool):
    """Tool for booking appointments"""
    name: str = "bookAppointment"
    description: str = """Book an appointment after collecting all required customer information.
    Use this tool ONLY after you have collected and confirmed ALL required information from the customer.
    
    DO NOT use this tool if a booking has already been confirmed in the conversation unless the customer explicitly asks for a new/additional booking."""
    args_schema: Type[BaseModel] = BookAppointmentInput
    
    _business: Any = PrivateAttr()
    _client_phone_number: Optional[str] = PrivateAttr(default=None)
    _session_key: Optional[str] = PrivateAttr(default=None)
    
    def __init__(self, business=None, client_phone_number=None, session_key=None, **kwargs):
        super().__init__(**kwargs)
        self._business = business
        self._client_phone_number = client_phone_number
        self._session_key = session_key
    
    def _run(self, firstName: str, phoneNumber: str, address1: str, city: str, state: str,
             serviceType: str, appointmentDateTime: str, bedrooms: int, bathrooms: int, 
             squareFeet: int, willSomeoneBeHome: str, email: str = None, zipCode: str = None,
             keyLocation: str = None, otherRequests: str = None, addonDishes: int = 0,
             addonLaundryLoads: int = 0, addonWindowCleaning: int = 0, addonPetsCleaning: int = 0,
             addonFridgeCleaning: int = 0, addonOvenCleaning: int = 0, addonBaseboard: int = 0,
             addonBlinds: int = 0, addonGreenCleaning: int = 0, addonCabinetsCleaning: int = 0,
             addonPatioSweeping: int = 0, addonGarageSweeping: int = 0, customAddons: dict = None) -> str:
        """Book an appointment with explicit parameters"""
        from ..api_views import book_appointment
        from ..models import Chat
        
        try:
            # Get or create chat
            if self._client_phone_number:
                from ..utils import find_by_phone_number
                chat = find_by_phone_number(Chat, 'clientPhoneNumber', self._client_phone_number, self._business)
                if not chat:
                    chat = Chat.objects.create(
                        business=self._business,
                        clientPhoneNumber=self._client_phone_number,
                        status='pending'
                    )
            elif self._session_key:
                chat = Chat.objects.filter(sessionKey=self._session_key, business=self._business).first()
                if not chat:
                    chat = Chat.objects.create(
                        business=self._business,
                        sessionKey=self._session_key,
                        status='pending'
                    )
            else:
                return json.dumps({"success": False, "error": "No client identifier provided"}, cls=DecimalEncoder)
            
            # Build booking data dictionary
            booking_data = {
                "firstName": firstName,
                "phoneNumber": phoneNumber,
                "email": email,
                "address1": address1,
                "city": city,
                "state": state,
                "zipCode": zipCode,
                "serviceType": serviceType,
                "appointmentDateTime": appointmentDateTime,
                "bedrooms": bedrooms,
                "bathrooms": bathrooms,
                "squareFeet": squareFeet,
                "willSomeoneBeHome": willSomeoneBeHome,
                "keyLocation": keyLocation,
                "otherRequests": otherRequests,
                "addonDishes": addonDishes,
                "addonLaundryLoads": addonLaundryLoads,
                "addonWindowCleaning": addonWindowCleaning,
                "addonPetsCleaning": addonPetsCleaning,
                "addonFridgeCleaning": addonFridgeCleaning,
                "addonOvenCleaning": addonOvenCleaning,
                "addonBaseboard": addonBaseboard,
                "addonBlinds": addonBlinds,
                "addonGreenCleaning": addonGreenCleaning,
                "addonCabinetsCleaning": addonCabinetsCleaning,
                "addonPatioSweeping": addonPatioSweeping,
                "addonGarageSweeping": addonGarageSweeping,
                "customAddons": customAddons if customAddons else {}
            }
            
            # Update chat summary with booking data
            chat.summary = booking_data
            chat.save()
            
            # Call book_appointment which reads from chat.summary
            result = book_appointment(
                self._business, 
                self._client_phone_number, 
                self._session_key
            )
            return json.dumps(result, cls=DecimalEncoder)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return json.dumps({"success": False, "error": str(e)}, cls=DecimalEncoder)


class GetCurrentTimeTool(BaseTool):
    """Tool for getting current time"""
    name: str = "current_time"
    description: str = """Get the current time in business timezone.
    Use this tool when a customer asks about current time, business hours, or what time it is."""
    args_schema: Type[BaseModel] = GetCurrentTimeInput
    
    _business: Any = PrivateAttr()
    
    def __init__(self, business=None, **kwargs):
        super().__init__(**kwargs)
        self._business = business
    
    def _run(self) -> str:
        """Get current time"""
        from ..api_views import get_current_time
        
        try:
            result = get_current_time(self._business)
            return result
        except Exception as e:
            return f"Error getting current time: {str(e)}"


class CalculateTotalTool(BaseTool):
    """Tool for calculating total cost"""
    name: str = "calculateTotal"
    description: str = """Calculate the total cost of the appointment.
    Use this tool before booking an appointment and after confirming all customer details.
    If the customer has an email address, the system will automatically check for custom pricing.
    Custom pricing takes precedence over standard pricing if available for that customer."""
    args_schema: Type[BaseModel] = CalculateTotalInput
    
    _business: Any = PrivateAttr()
    _client_phone_number: Optional[str] = PrivateAttr(default=None)
    _session_key: Optional[str] = PrivateAttr(default=None)
    
    def __init__(self, business=None, client_phone_number=None, session_key=None, **kwargs):
        super().__init__(**kwargs)
        self._business = business
        self._client_phone_number = client_phone_number
        self._session_key = session_key
    
    def _run(self, serviceType: str, bedrooms: int, bathrooms: int, squareFeet: int,
             email: str = None, addonDishes: int = 0, addonLaundryLoads: int = 0,
             addonWindowCleaning: int = 0, addonPetsCleaning: int = 0, addonFridgeCleaning: int = 0,
             addonOvenCleaning: int = 0, addonBaseboard: int = 0, addonBlinds: int = 0,
             addonGreenCleaning: int = 0, addonCabinetsCleaning: int = 0, addonPatioSweeping: int = 0,
             addonGarageSweeping: int = 0, customAddons: dict = None) -> str:
        """Calculate total cost with explicit parameters"""
        from ..api_views import calculate_total
        from ..models import Chat
        
        try:
            # Get or create chat
            if self._client_phone_number:
                from ..utils import find_by_phone_number
                chat = find_by_phone_number(Chat, 'clientPhoneNumber', self._client_phone_number, self._business)
                if not chat:
                    chat = Chat.objects.create(
                        business=self._business,
                        clientPhoneNumber=self._client_phone_number,
                        status='pending'
                    )
            elif self._session_key:
                chat = Chat.objects.filter(sessionKey=self._session_key, business=self._business).first()
                if not chat:
                    chat = Chat.objects.create(
                        business=self._business,
                        sessionKey=self._session_key,
                        status='pending'
                    )
            else:
                return json.dumps({"success": False, "error": "No client identifier provided"}, cls=DecimalEncoder)
            
            # Build calculation data dictionary
            calc_data = {
                "serviceType": serviceType,
                "bedrooms": bedrooms,
                "bathrooms": bathrooms,
                "squareFeet": squareFeet,
                "email": email,
                "addonDishes": addonDishes,
                "addonLaundryLoads": addonLaundryLoads,
                "addonWindowCleaning": addonWindowCleaning,
                "addonPetsCleaning": addonPetsCleaning,
                "addonFridgeCleaning": addonFridgeCleaning,
                "addonOvenCleaning": addonOvenCleaning,
                "addonBaseboard": addonBaseboard,
                "addonBlinds": addonBlinds,
                "addonGreenCleaning": addonGreenCleaning,
                "addonCabinetsCleaning": addonCabinetsCleaning,
                "addonPatioSweeping": addonPatioSweeping,
                "addonGarageSweeping": addonGarageSweeping,
                "customAddons": customAddons if customAddons else {}
            }
            
            # Update chat summary with calculation data
            current_summary = chat.summary if chat.summary else {}
            current_summary.update(calc_data)
            chat.summary = current_summary
            chat.save()
            
            # Call calculate_total which reads from chat.summary
            result = calculate_total(
                self._business,
                self._client_phone_number,
                self._session_key
            )
            return json.dumps(result, cls=DecimalEncoder)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return json.dumps({"success": False, "error": str(e)}, cls=DecimalEncoder)


class RescheduleAppointmentTool(BaseTool):
    """Tool for rescheduling appointments"""
    name: str = "reschedule_appointment"
    description: str = """Reschedule an existing appointment to a new date and time.
    Use this tool when a customer wants to change the date/time of an existing booking.
    You must have the booking ID before using this tool."""
    args_schema: Type[BaseModel] = RescheduleAppointmentInput
    
    def _run(self, booking_id: str, new_date_time: str, reason: Optional[str] = None) -> str:
        """Reschedule an appointment"""
        from ..api_views import reschedule_appointment
        
        try:
            result = reschedule_appointment(booking_id, new_date_time, reason)
            return json.dumps(result, cls=DecimalEncoder)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, cls=DecimalEncoder)


class CancelAppointmentTool(BaseTool):
    """Tool for canceling appointments"""
    name: str = "cancel_appointment"
    description: str = """Cancel an existing appointment.
    Use this tool when a customer wants to cancel their appointment.
    You must have the booking ID before using this tool."""
    args_schema: Type[BaseModel] = CancelAppointmentInput
    
    def _run(self, booking_id: str, reason: str) -> str:
        """Cancel an appointment"""
        from ..api_views import cancel_appointment
        
        try:
            result = cancel_appointment(booking_id, reason)
            return json.dumps(result, cls=DecimalEncoder)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, cls=DecimalEncoder)
