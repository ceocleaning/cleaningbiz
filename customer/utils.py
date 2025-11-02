from customer.models import Customer


def create_customer(data, business):
    """
    Create or get a customer and link them to a business.
    Uses ManyToMany relationship - same customer data across all businesses.
    """
    customer_email = data.get("email", "")
    
    if not customer_email:
        return None
    
    # Try to find existing customer by email
    customer = Customer.objects.filter(email=customer_email).first()
    
    if not customer:
        # Create new customer
        customer = Customer.objects.create(
            first_name=data.get("firstName") or data.get("first_name", ""),
            last_name=data.get("lastName") or data.get("last_name", ""),
            email=customer_email,
            phone_number=data.get("phoneNumber") or data.get("phone_number", ""),
            address=data.get("address1") or data.get("address", ""),
            city=data.get("city", ""),
            state_or_province=data.get("state") or data.get('stateOrProvince', ""),
            zip_code=data.get("zipCode", data.get("zip_code", ""))
        )
    
    # Link customer to this business if not already linked
    if business not in customer.businesses.all():
        customer.businesses.add(business)
    
    return customer