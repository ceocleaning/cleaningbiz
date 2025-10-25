from customer.models import Customer


def create_customer(data, business):
    customer_email = data.get("email", "")
    customer = None
    
    if customer_email:
        customer = Customer.objects.filter(email=customer_email, business=business)
        
    
        if not customer.exists():
            customer = Customer.objects.create(
            business=business,
            first_name=data["firstName"] or data["first_name"],
            last_name=data["lastName"] or data["last_name"],
            email=customer_email,
            phone_number=data["phoneNumber"] or data["phone_number"],
            address=data["address1"] or data["address"],
            city=data["city"],
            state_or_province=data["state"] or data['stateOrProvince'],
            zip_code=data.get("zipCode", data.get("zip_code", ""))
            )
        else:
            customer = customer.first()
    
    return customer