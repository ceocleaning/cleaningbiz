from customer.models import Customer


def create_customer(data, business):
    customer_email = data.get("email", "")
    customer = None
    
    if customer_email:
        customer = Customer.objects.filter(email=customer_email, business=business)
        
    
        if not customer.exists():
            customer = Customer.objects.create(
            business=business,
            first_name=data.get("firstName") or data.get("first_name", ""),
            last_name=data.get("lastName") or data.get("last_name", ""),
            email=customer_email,
            phone_number=data.get("phoneNumber") or data.get("phone_number", ""),
            address=data.get("address1") or data.get("address", ""),
            city=data.get("city", ""),
            state_or_province=data.get("state") or data.get('stateOrProvince', ""),
            zip_code=data.get("zipCode", data.get("zip_code", ""))
            )
        else:
            customer = customer.first()
    
    return customer