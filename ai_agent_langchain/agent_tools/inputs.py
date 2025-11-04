from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class CheckAvailabilityInput(BaseModel):
    """Input for checking availability."""
    date: str = Field(..., description="The date to check availability in format YYYY-MM-DD")
    time: Optional[str] = Field(None, description="The time to check availability in format HH:MM")
    service_name: Optional[str] = Field(None, description="Name of the service")
    business_id: Optional[str] = Field(None, description="ID of the business (automatically provided)")
    duration_minutes: Optional[int] = Field(None, description="Duration of the appointment in minutes")

class BookAppointmentInput(BaseModel):
    """Input for booking an appointment."""
    date: str = Field(..., description="The date for the appointment in format YYYY-MM-DD")
    time: str = Field(..., description="The time for the appointment in format HH:MM")
    service_name: str = Field(..., description="Name of the service")
    business_id: Optional[str] = Field(None, description="ID of the business (automatically provided)")
    customer_name: str = Field(..., description="Name of the customer")
    customer_phone: str = Field(..., description="Phone number of the customer")
    customer_email: Optional[str] = Field(None, description="Email of the customer")
    service_items: Optional[List[Dict[str, Any]]] = Field(None, description="List of service items with their values. Format: [{'identifier': 'item_id', 'value': 'user_value', 'quantity': 1}]. For number fields, value is the quantity. For boolean, value is 'yes' or 'no'. For select, value is the selected option. For text/textarea, value is the text input.")
    notes: Optional[str] = Field(None, description="Additional notes for the appointment")

class RescheduleAppointmentInput(BaseModel):
    """Input for rescheduling an appointment."""
    booking_id: str = Field(..., description="ID of the booking to reschedule")
    new_date: str = Field(..., description="The new date for the appointment in format YYYY-MM-DD")
    new_time: str = Field(..., description="The new time for the appointment in format HH:MM")
    business_id: Optional[str] = Field(None, description="ID of the business (automatically provided)")

class CancelAppointmentInput(BaseModel):
    """Input for canceling an appointment."""
    booking_id: str = Field(..., description="ID of the booking to cancel")
    business_id: Optional[str] = Field(None, description="ID of the business (automatically provided)")
    reason: Optional[str] = Field(None, description="Reason for cancellation")

class GetServiceItemsInput(BaseModel):
    """Input for getting available service items."""
    business_id: Optional[str] = Field(None, description="ID of the business (automatically provided)")
    service_name: Optional[str] = Field(None, description="Name of the service to filter items by")

