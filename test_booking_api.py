import requests
import json

# Base URL - change this to your actual server URL when testing
BASE_URL = "http://localhost:8000"

def test_get_business_info(business_id):
    """Test the GET endpoint to retrieve business information and pricing"""
    url = f"{BASE_URL}/customer/api/booking/{business_id}/"
    
    print(f"Testing GET request to {url}")
    response = requests.get(url)
    
    if response.status_code == 200:
        print("Success! Business information retrieved:")
        print(json.dumps(response.json(), indent=2))
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None

def test_create_booking(business_id, booking_data):
    """Test the POST endpoint to create a booking"""
    url = f"{BASE_URL}/customer/api/booking/{business_id}/"
    
    print(f"Testing POST request to {url}")
    response = requests.post(url, json=booking_data)
    
    if response.status_code == 201:
        print("Success! Booking created:")
        print(json.dumps(response.json(), indent=2))
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None

if __name__ == "__main__":
    # Replace with an actual business ID from your database
    business_id = "BUS-3486"
    
    # First, get the business information
    business_info = test_get_business_info(business_id)
    
    if business_info:
        # Sample booking data - update with actual values
        booking_data = {
            "firstName": "John",
            "lastName": "Doe",
            "email": "john.doe@example.com",
            "phoneNumber": "555-123-4567",
            "address": "123 Main St",
            "city": "Anytown",
            "stateOrProvince": "CA",
            "zipCode": "12345",
            "bedrooms": 3,
            "bathrooms": 2,
            "squareFeet": 1500,
            "serviceType": "standard",
            "cleaningDate": "2025-10-15",
            "startTime": "14:00",
            "recurring": "onetime",
            "otherRequests": "Please clean the windows thoroughly",
            "totalAmount": 150.00,
            "tax": 12.50,
            "addonDishes": 1,
            "addonLaundryLoads": 0,
            "addonWindowCleaning": 1,
            "addonPetsCleaning": 0,
            "addonFridgeCleaning": 0,
            "addonOvenCleaning": 0,
            "addonBaseboard": 0,
            "addonBlinds": 0,
            # Add custom addons if needed
            # "custom_addon_qty_1": 2
        }
        
        # Create the booking
        test_create_booking(business_id, booking_data)
