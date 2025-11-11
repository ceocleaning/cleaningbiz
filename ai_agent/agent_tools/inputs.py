from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union

class CheckAvailabilityInput(BaseModel):
    """Input for checking availability."""
    date: str = Field(..., description="The date to check availability (e.g., 'Tomorrow at 2 PM', 'March 15, 2025 at 10 AM')")

class BookAppointmentInput(BaseModel):
    """Input for booking an appointment. Collect ALL required information before calling this tool."""
    firstName: str = Field(..., description="Customer's first name")
    phoneNumber: str = Field(..., description="Customer's phone number")
    email: Optional[str] = Field(None, description="Customer's email address")
    address1: str = Field(..., description="Customer's street address")
    city: str = Field(..., description="Customer's city")
    state: str = Field(..., description="Customer's state")
    zipCode: Optional[str] = Field(None, description="Customer's zip code")
    serviceType: str = Field(..., description="Type of service (e.g., 'standard', 'deep', 'moveinout', 'airbnb')")
    appointmentDateTime: str = Field(..., description="Appointment date and time (e.g., 'Tomorrow at 2 PM', 'March 15, 2025 at 10 AM')")
    bedrooms: int = Field(..., description="Number of bedrooms")
    bathrooms: int = Field(..., description="Number of bathrooms")
    squareFeet: int = Field(..., description="Square footage of the property")
    willSomeoneBeHome: str = Field(..., description="Will someone be home during cleaning? ('yes' or 'no')")
    keyLocation: Optional[str] = Field(None, description="Where is the key located if no one will be home?")
    otherRequests: Optional[str] = Field(None, description="Any other special requests or notes")
    # Add-ons (all optional, default to 0)
    addonDishes: Optional[int] = Field(0, description="Number of dish loads")
    addonLaundryLoads: Optional[int] = Field(0, description="Number of laundry loads")
    addonWindowCleaning: Optional[int] = Field(0, description="Number of windows to clean")
    addonPetsCleaning: Optional[int] = Field(0, description="Pet cleaning add-on")
    addonFridgeCleaning: Optional[int] = Field(0, description="Fridge cleaning add-on")
    addonOvenCleaning: Optional[int] = Field(0, description="Oven cleaning add-on")
    addonBaseboard: Optional[int] = Field(0, description="Baseboard cleaning add-on")
    addonBlinds: Optional[int] = Field(0, description="Blinds cleaning add-on")
    addonGreenCleaning: Optional[int] = Field(0, description="Green cleaning add-on")
    addonCabinetsCleaning: Optional[int] = Field(0, description="Cabinets cleaning add-on")
    addonPatioSweeping: Optional[int] = Field(0, description="Patio sweeping add-on")
    addonGarageSweeping: Optional[int] = Field(0, description="Garage sweeping add-on")
    customAddons: Optional[Dict[str, int]] = Field(None, description="Custom business-specific add-ons as a dictionary with addon data name as key and quantity as value. Example: {'custom_addon_name': 1}")

class GetCurrentTimeInput(BaseModel):
    """Input for getting current time."""
    pass  # No parameters needed

class CalculateTotalInput(BaseModel):
    """Input for calculating total cost. Provide all booking details to get accurate pricing."""
    serviceType: str = Field(..., description="Type of service (e.g., 'standard', 'deep', 'moveinout', 'airbnb')")
    bedrooms: int = Field(..., description="Number of bedrooms")
    bathrooms: int = Field(..., description="Number of bathrooms")
    squareFeet: int = Field(..., description="Square footage of the property")
    email: Optional[str] = Field(None, description="Customer's email (to check for custom pricing)")
    # Add-ons (all optional, default to 0)
    addonDishes: Optional[int] = Field(0, description="Number of dish loads")
    addonLaundryLoads: Optional[int] = Field(0, description="Number of laundry loads")
    addonWindowCleaning: Optional[int] = Field(0, description="Number of windows to clean")
    addonPetsCleaning: Optional[int] = Field(0, description="Pet cleaning add-on")
    addonFridgeCleaning: Optional[int] = Field(0, description="Fridge cleaning add-on")
    addonOvenCleaning: Optional[int] = Field(0, description="Oven cleaning add-on")
    addonBaseboard: Optional[int] = Field(0, description="Baseboard cleaning add-on")
    addonBlinds: Optional[int] = Field(0, description="Blinds cleaning add-on")
    addonGreenCleaning: Optional[int] = Field(0, description="Green cleaning add-on")
    addonCabinetsCleaning: Optional[int] = Field(0, description="Cabinets cleaning add-on")
    addonPatioSweeping: Optional[int] = Field(0, description="Patio sweeping add-on")
    addonGarageSweeping: Optional[int] = Field(0, description="Garage sweeping add-on")
    customAddons: Optional[Dict[str, int]] = Field(None, description="Custom business-specific add-ons as a dictionary with addon data name as key and quantity as value. Example: {'custom_addon_name': 1}")

class RescheduleAppointmentInput(BaseModel):
    """Input for rescheduling an appointment."""
    booking_id: str = Field(..., description="The booking ID of the appointment to reschedule")
    new_date_time: str = Field(..., description="The new date and time for the appointment (e.g., 'Tomorrow at 2 PM', 'March 15, 2025 at 10 AM')")
    reason: Optional[str] = Field(None, description="The reason for rescheduling the appointment")

class CancelAppointmentInput(BaseModel):
    """Input for canceling an appointment."""
    booking_id: str = Field(..., description="The booking ID of the appointment to cancel")
    reason: str = Field(..., description="The reason for canceling the appointment")
