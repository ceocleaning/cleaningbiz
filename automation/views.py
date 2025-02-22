from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from .models import Lead
from .utils import sendInvoicetoClient
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import os
import json
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from retell import Retell

from .models import Lead
from datetime import datetime

from bookings.models import Booking, Invoice, Payment
from accounts.models import ApiCredential




@login_required(login_url='accounts:login')
def home(request):
    # Get the user's business
    business = request.user.business_set.first()

    if not business:
        return redirect('accounts:register_business')

    bookings = Booking.objects.filter(business=business).order_by('-createdAt')
    leads = Lead.objects.filter(business=business).order_by('-createdAt')
    converted_leads = leads.filter(isConverted=True)
    total_leads = leads.count()
    credentials = ApiCredential.objects.filter(business=business).first()

    context = {
        'leads': leads, 
        'bookings': bookings,
        'credentials': credentials,
        'total_leads': total_leads,
        'converted_leads': converted_leads.count(),
        'total_bookings': bookings.count()
    }
    return render(request, 'home.html', context)    







@login_required
def all_leads(request):
    leads = Lead.objects.filter(business__user=request.user).order_by('-createdAt')
    context = {
        'leads': leads
    }
    return render(request, 'leads.html', context)


@login_required
def lead_detail(request, leadId):
    lead = get_object_or_404(Lead, leadId=leadId)
    context = {
        'lead': lead
    }
    return render(request, 'lead_detail.html', context)


@login_required
def create_lead(request):
    if request.method == 'POST':
        try:
            lead = Lead.objects.create(
              
                name=request.POST.get('name'),
                email=request.POST.get('email'),
                phone_number=request.POST.get('phone_number'),
                source=request.POST.get('source'),
                notes=request.POST.get('notes'),
                content=request.POST.get('content'),
                business=request.user.business_set.first()
            )
            messages.success(request, f'Lead {lead.leadId} created successfully!')
            return redirect('lead_detail', leadId=lead.leadId)
        except Exception as e:
            messages.error(request, f'Error creating lead: {str(e)}')
            return redirect('create_lead')
    
    return render(request, 'create_lead.html')


@login_required
def update_lead(request, leadId):
    lead = get_object_or_404(Lead, leadId=leadId)
    
    if request.method == 'POST':
        try:
            lead.name = request.POST.get('name')
            lead.email = request.POST.get('email')
            lead.phone_number = request.POST.get('phone_number')
            lead.source = request.POST.get('source')
            lead.notes = request.POST.get('notes')
            lead.content = request.POST.get('content')
            lead.isConverted = 'isConverted' in request.POST
            lead.save()
            
            messages.success(request, f'Lead {lead.leadId} updated successfully!')
            return redirect('lead_detail', leadId=lead.leadId)
        except Exception as e:
            messages.error(request, f'Error updating lead: {str(e)}')
    
    context = {
        'lead': lead
    }
    return render(request, 'update_lead.html', context)


@login_required
def delete_lead(request, leadId):
    lead = get_object_or_404(Lead, leadId=leadId)
    
    if request.method == 'POST':
        try:
            lead.delete()
            messages.success(request, 'Lead deleted successfully!')
            return redirect('all_leads')
        except Exception as e:
            messages.error(request, f'Error deleting lead: {str(e)}')
            return redirect('lead_detail', leadId=leadId)
    
    return redirect('lead_detail', leadId=leadId)
