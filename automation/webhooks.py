from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt    
from django.db import transaction
from django.core.cache import cache
from asgiref.sync import sync_to_async
import json
import requests
import threading

from accounts.models import ApiCredential, Business, BusinessSettings, BookingIntegration, CustomAddons
from bookings.models import Booking, Invoice, Payment
from .utils import calculateAmount, calculateAddonsAmount



@csrf_exempt
def thumbtack_webhook(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        print(data)
    
    return JsonResponse({'status': 'success'}, status=200)




@csrf_exempt
def handle_retell_webhook(request, secretKey):
    """Handle incoming Retell webhook requests"""
    if request.method != 'POST':
        return HttpResponse(status=405)
        
    try:
        if not request.body:
            return HttpResponse(status=400)
        
        # Quick validation of credentials
        apiCredentialObj = ApiCredential.objects.filter(secretKey=secretKey).first()
        if not apiCredentialObj:
            return HttpResponse(status=401)  # Unauthorized
            
        # Parse and validate basic request structure
        post_data = json.loads(request.body)
        event = post_data.get("event")
        if not event:
            return HttpResponse(status=400)
            
        # Start processing in a background thread
        webhook_data = {
            "post_data": post_data,
            "api_credential_id": apiCredentialObj.id
        }
        thread = threading.Thread(target=process_webhook_data, args=(webhook_data,))
        thread.start()
        
        # Return immediate success response
        return HttpResponse(status=200)

    except json.JSONDecodeError:
        return HttpResponse(status=400)
    except Exception as e:
        return HttpResponse(status=500)

@transaction.atomic
def process_webhook_data(webhook_data):
    """Process webhook data in a background thread"""
    try:
        post_data = webhook_data["post_data"]
        api_credential_id = webhook_data["api_credential_id"]
        
        # Get API credentials and business
        apiCredentialObj = ApiCredential.objects.get(id=api_credential_id)
        businessObj = apiCredentialObj.business
        
        event = post_data.get("event")
        if event == "call_analyzed":
            call_analysis = post_data.get("call", {}).get("call_analysis", {})
            custom_data = call_analysis.get("custom_analysis_data", {})

            isAppointmentBooked = custom_data.get("appointment_booked", False)

            if not isAppointmentBooked:
                print("Appointment not booked")
                return
            
            # Extract customer data
            customer_data = {
                "firstName": custom_data.get("first_name", ""),
                "lastName": custom_data.get("last_name", ""),
                "email": custom_data.get("email", ""),
                "phoneNumber": custom_data.get("phone_number", ""),
                "state": custom_data.get("state", ""),
                "zipCode": custom_data.get("zip_code", ""),
                "city": custom_data.get("city", ""),
                "address1": custom_data.get("address", ""),
                "address2": "",
                "service_type": custom_data.get("service_type", ""),
                "appointmentDateTime": custom_data.get("cleaning_date_time", ""),
                "bedrooms": int(custom_data.get("bedrooms", 0)),
                "bathrooms": int(custom_data.get("bathrooms", 0)),
                "area": int(custom_data.get("area", 0)),
                "additionalRequests": custom_data.get('additional_requests')
            }
            print(customer_data)
            # Get business settings
            businessSettingsObj = BusinessSettings.objects.get(business=businessObj)


            serviceType = customer_data["service_type"].lower().replace(" ", "")

            if 'regular' in serviceType:
                serviceType = 'standard'
            elif 'deep' in serviceType:
                serviceType = 'deep'
            elif 'moveinmoveout' in serviceType:
                serviceType = 'moveinmoveout'
            elif 'airbnb' in serviceType:
                serviceType = 'airbnb'
            
            # Calculate base price
            calculateTotal = calculateAmount(
                customer_data["bedrooms"],
                customer_data["bathrooms"],
                customer_data["area"],
                serviceType,
                businessSettingsObj
            )

            print(calculateTotal)
            
            # Process addons
            addons = {
                "dishes": int(custom_data.get("dishes", 0)),
                "laundry": int(custom_data.get("laundry", 0)),
                "windows": int(custom_data.get("windows", 0)),
                "pets": int(custom_data.get("pets", 0)),
                "fridge": int(custom_data.get("fridge", 0)),
                "oven": int(custom_data.get("oven", 0)),
                "baseboards": int(custom_data.get("baseboards", 0)),
                "blinds": int(custom_data.get("blinds", 0)),
                "green": int(custom_data.get("green", 0)),
                "cabinets": int(custom_data.get("cabinets", 0)),
                "patio": int(custom_data.get("patio", 0)),
                "garage": int(custom_data.get("garage", 0))
            }

            print(f"Addons: {addons}")
            
            addonsPrices = {
                "dishes": businessSettingsObj.addonPriceDishes,
                "laundry": businessSettingsObj.addonPriceLaundry,
                "windows": businessSettingsObj.addonPriceWindow,
                "pets": businessSettingsObj.addonPricePets,
                "fridge": businessSettingsObj.addonPriceFridge,
                "oven": businessSettingsObj.addonPriceOven,
                "baseboards": businessSettingsObj.addonPriceBaseboard,
                "blinds": businessSettingsObj.addonPriceBlinds,
                "green": businessSettingsObj.addonPriceGreen,
                "cabinets": businessSettingsObj.addonPriceCabinets,
                "patio": businessSettingsObj.addonPricePatio,
                "garage": businessSettingsObj.addonPriceGarage
            }

            print(f"Addons prices: {addonsPrices}")

            # Calculate custom addons
            customAddonsObj = CustomAddons.objects.filter(business=businessObj)
            bookingCustomAddons = []
            customAddonTotal = 0
            for customAddon in customAddonsObj:
                if customAddon.addonName not in addons:
                    if customAddonsObj.filter(addonName=customAddon.addonName).exists():
                        createNewBookingAddon = BookingCustomAddons.objects.create(
                            addon=customAddon,
                            qty=custom_data.get(customAddon.addonName, 0)
                        )
                        bookingCustomAddons.append(createNewBookingAddon)
                        customAddonTotal += customAddon.addonPrice * custom_data.get(customAddon.addonName, 0)

            print(f"Custom addons total: {customAddonTotal}")
            
            # Calculate final amounts
            addons_result = calculateAddonsAmount(addons, addonsPrices)
            print(f"Addons result: {addons_result}")
            final_total = calculateTotal + addons_result + customAddonTotal
            print(f"Final total: {final_total}")
            
            # Create booking
            newBooking = Booking.objects.create(
                business=businessObj,
                firstName=customer_data["firstName"],
                lastName=customer_data["lastName"],
                email=customer_data["email"],
                phoneNumber=customer_data["phoneNumber"],
                address1=customer_data["address1"],
                address2=customer_data["address2"],
                city=customer_data["city"],
                stateOrProvince=customer_data["state"],
                zipCode=customer_data["zipCode"],
                cleaningDateTime=customer_data["appointmentDateTime"],
                serviceType=serviceType,
                bedrooms=customer_data["bedrooms"],
                bathrooms=customer_data["bathrooms"],
                squareFeet=customer_data["area"],
                otherRequests=customer_data["additionalRequests"],
                totalPrice=final_total,
                addonDishes=addons["dishes"],
                addonLaundryLoads=addons["laundry"],
                addonWindowCleaning=addons["windows"],
                addonPetsCleaning=addons["pets"],
                addonFridgeCleaning=addons["fridge"],
                addonOvenCleaning=addons["oven"],
                addonBaseboard=addons["baseboards"],
                addonBlinds=addons["blinds"],
                addonGreenCleaning=addons["green"],
                addonCabinetsCleaning=addons["cabinets"],
                addonPatioSweeping=addons["patio"],
                addonGarageSweeping=addons["garage"]
            )


            newBooking.customAddons.set(bookingCustomAddons)
            newBooking.save()

            print("Booking Id: ", newBooking.bookingId)
            
            # Send booking data to integration
            send_booking_data(newBooking)
            
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")


def send_booking_data(booking):
    """Send booking data to integration webhook"""
    try:
        integrationObj = BookingIntegration.objects.filter(business=booking.business).first()
        if not integrationObj or not integrationObj.webhookUrl:
            return

        payload = {
            "firstName": booking.firstName,
            "lastName": booking.lastName,
            "email": booking.email,
            "phoneNumber": booking.phoneNumber,
            "address1": booking.address1,
            "address2": booking.address2,
            "city": booking.city,
            "stateOrProvince": booking.stateOrProvince,
            "zipCode": booking.zipCode,
            "bedrooms": booking.bedrooms,
            "bathrooms": booking.bathrooms,
            "squareFeet": booking.squareFeet,
            "serviceType": booking.serviceType,
            "cleaningDate": booking.cleaningDateTime.date(),
            "startTime": booking.cleaningDateTime.time(),
            "endTime": (booking.cleaningDateTime + timedelta(minutes=60)).time(),
            "totalPrice": float(booking.totalPrice),
            "tax": float(booking.tax or 0),
            "addonDishes": booking.addonDishes,
            "addonLaundryLoads": booking.addonLaundryLoads,
            "addonWindowCleaning": booking.addonWindowCleaning,
            "addonPetsCleaning": booking.addonPetsCleaning,
            "addonFridgeCleaning": booking.addonFridgeCleaning,
            "addonOvenCleaning": booking.addonOvenCleaning,
            "addonBaseboard": booking.addonBaseboard,
            "addonBlinds": booking.addonBlinds,
            "addonGreenCleaning": booking.addonGreenCleaning,
            "addonCabinetsCleaning": booking.addonCabinetsCleaning,
            "addonPatioSweeping": booking.addonPatioSweeping,
            "addonGarageSweeping": booking.addonGarageSweeping
        }

        response = requests.post(
            integrationObj.webhookUrl,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()
        print("Successfully sent booking data to integration", response.text)
        return response

    except Exception as e:
        print(f"Error sending booking data: {str(e)}")
        return None