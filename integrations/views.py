from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import PlatformIntegration, DataMapping
from accounts.models import Business
from bookings.models import Booking
import json

# Create your views here.

@login_required
def integration_list(request):
    business = request.user.business_set.first()
    if not business:
        return redirect('accounts:register_business')

    integrations = PlatformIntegration.objects.filter(business=business)
    return render(request, 'integrations/integration_list.html', {
        'integrations': integrations
    })

@login_required
def add_integration(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        base_url = request.POST.get('base_url')
        auth_type = request.POST.get('auth_type')
        is_active = request.POST.get('is_active') == 'on'
        
        # Get auth data based on type
        auth_data = {}
        if auth_type == 'token':
            auth_data['token'] = request.POST.get('auth_token')
        elif auth_type == 'basic':
            auth_data['username'] = request.POST.get('username')
            auth_data['password'] = request.POST.get('password')

        # Create new integration
        integration = PlatformIntegration.objects.create(
            name=name,
            base_url=base_url,
            auth_type=auth_type,
            auth_data=auth_data,
            is_active=is_active,
            business=request.user.business_set.first()
        )

        messages.success(request, 'Integration added successfully!')
        return redirect('integration_list')

    auth_types = PlatformIntegration._meta.get_field('auth_type').choices
    
    context = {
        'auth_types': auth_types,
        'integration': None
    }
    
    return render(request, 'integrations/add_integration.html', context)

@login_required
def integration_mapping(request, platform_id):
    platform = get_object_or_404(PlatformIntegration, id=platform_id, business=request.user.business_set.first())
    mappings = DataMapping.objects.filter(platform=platform)
    
    if request.method == 'POST':
        data = json.loads(request.body)
        mappings_data = data.get('mappings', [])
        
        # Delete existing mappings
        DataMapping.objects.filter(platform=platform).delete()
        
        # Create new mappings
        for mapping_data in mappings_data:
            DataMapping.objects.create(
                platform=platform,
                source_field=mapping_data['source_field'],
                target_field=mapping_data['target_field'],
                parent_path=mapping_data.get('parent_path'),
                field_type=mapping_data.get('field_type', 'string'),
                default_value=mapping_data.get('default_value', ''),
                is_required=mapping_data.get('is_required', False),
                transformation_rule=mapping_data.get('transformation_rule')
            )
        
        return JsonResponse({'status': 'success'})

    # Get all available fields from Booking model
    booking_fields = []
    for field in Booking._meta.get_fields():
        if not field.is_relation and not field.auto_created:
            booking_fields.append((field.name, field.verbose_name or field.name.replace('_', ' ').title()))

    field_types = [
        ('string', 'Text'),
        ('number', 'Number'),
        ('boolean', 'True/False'),
        ('date', 'Date'),
        ('time', 'Time'),
        ('datetime', 'Date & Time'),
        ('array', 'Array/List'),
        ('object', 'Object')
    ]

    context = {
        'platform': platform,
        'mappings': mappings,
        'booking_fields': booking_fields,
        'field_types': field_types
    }

    return render(request, 'integrations/mapping.html', context)

@login_required
def preview_mapping(request, platform_id):
    platform = get_object_or_404(PlatformIntegration, id=platform_id, business=request.user.business_set.first())
    mappings = DataMapping.objects.filter(platform=platform)
    
    # Get a sample booking
    sample_booking = Booking.objects.filter(business=request.user.business_set.first()).first()
    
    if not sample_booking:
        # Create a dummy booking for preview if none exists
        sample_booking = Booking(
            firstName="John",
            lastName="Doe",
            email="john@example.com",
            phoneNumber="123-456-7890",
            address1="123 Main St",
            city="Sample City",
            stateOrProvince="State",
            zipCode="12345",
            bedrooms=3,
            bathrooms=2,
            serviceType="standard",
            cleaningDate="2025-03-01",
            totalPrice="150.00"
        )

    # Prepare sample booking data
    sample_data = {
        'firstName': sample_booking.firstName,
        'lastName': sample_booking.lastName,
        'email': sample_booking.email,
        'phoneNumber': sample_booking.phoneNumber,
        'address1': sample_booking.address1,
        'city': sample_booking.city,
        'stateOrProvince': sample_booking.stateOrProvince,
        'zipCode': sample_booking.zipCode,
        'bedrooms': sample_booking.bedrooms,
        'bathrooms': sample_booking.bathrooms,
        'serviceType': sample_booking.serviceType,
        'cleaningDate': sample_booking.cleaningDate,
        'totalPrice': sample_booking.totalPrice
    }

    # Generate mapped data
    mapped_data = {}
    required_fields = set()
    
    # Group mappings by type (flat vs nested)
    grouped_mappings = {
        'Flat': [],
        'Nested': []
    }
    
    for mapping in mappings:
        value = getattr(sample_booking, mapping.source_field, mapping.default_value)
        
        # Track required fields
        if mapping.is_required:
            required_fields.add(mapping.source_field)
        
        # Apply any transformation rules
        if mapping.transformation_rule:
            try:
                # Example transformation: {"operation": "uppercase"}
                if mapping.transformation_rule.get('operation') == 'uppercase' and value:
                    value = str(value).upper()
                # Add more transformations as needed
            except Exception as e:
                print(f"Error applying transformation: {e}")

        # Handle nested paths
        if mapping.parent_path:
            path_parts = mapping.parent_path.split('.')
            current_dict = mapped_data
            
            # Create nested structure
            for part in path_parts:
                if part not in current_dict:
                    current_dict[part] = {}
                current_dict = current_dict[part]
            
            current_dict[mapping.target_field] = value
            grouped_mappings['Nested'].append(mapping)
        else:
            mapped_data[mapping.target_field] = value
            grouped_mappings['Flat'].append(mapping)

    # Remove empty groups
    grouped_mappings = {k: v for k, v in grouped_mappings.items() if v}

    context = {
        'platform': platform,
        'mapped_data': mapped_data,
        'sample_booking': sample_data,
        'grouped_mappings': grouped_mappings,
        'required_fields': required_fields
    }

    return render(request, 'integrations/preview_mapping.html', context)

@login_required
def edit_integration(request, platform_id):
    platform = get_object_or_404(PlatformIntegration, id=platform_id, business=request.user.business_set.first())
    
    if request.method == 'POST':
        platform.name = request.POST.get('name')
        platform.base_url = request.POST.get('base_url')
        platform.auth_type = request.POST.get('auth_type')
        platform.is_active = request.POST.get('is_active') == 'on'
        
        auth_data = {}
        if platform.auth_type == 'token':
            auth_data = {
                'token': request.POST.get('auth_token')
            }
        elif platform.auth_type == 'basic':
            auth_data = {
                'username': request.POST.get('username'),
                'password': request.POST.get('password')
            }
        
        platform.auth_data = auth_data
        platform.save()
        
        messages.success(request, 'Integration updated successfully!')
        return redirect('integration_list')
    
    # Get choices from model
    auth_types = PlatformIntegration._meta.get_field('auth_type').choices
    
    return render(request, 'integrations/add_integration.html', {
        'integration': platform,
        'auth_types': auth_types
    })

@login_required
def delete_integration(request, platform_id):
    platform = get_object_or_404(PlatformIntegration, id=platform_id, business=request.user.business_set.first())
    if request.method == 'POST':
        platform.delete()
        messages.success(request, 'Integration deleted successfully!')
        return redirect('integration_list')
    
    return render(request, 'integrations/delete_confirmation.html', {
        'platform': platform
    })
