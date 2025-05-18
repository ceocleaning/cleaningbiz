from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Count, Q

from accounts.models import Business, CleanerProfile
from bookings.models import Booking
from bookings.payout_models import CleanerPayout, PAYOUT_STATUS_CHOICES


@login_required
def payouts_dashboard(request):
    """
    Main dashboard view for payouts - shows different views for business owners vs cleaners
    """
    # Check if user is a business owner
    is_business_owner = Business.objects.filter(user=request.user).exists()
    
    # Check if user is a cleaner
    is_cleaner = CleanerProfile.objects.filter(user=request.user).exists()
    
    if is_business_owner:
        # Business owner view - show all cleaners and their payouts
        business = Business.objects.get(user=request.user)
        
        # Get all cleaners for this business through cleaner profiles
        cleaner_profiles = CleanerProfile.objects.filter(business=business)
        
        # Check if a specific cleaner is selected for filtering
        selected_cleaner_id = request.GET.get('cleaner_id', '')
        selected_cleaner_profile = None
        
        # Base queryset for payouts
        payouts_queryset = CleanerPayout.objects.filter(business=business)
        
        # Apply cleaner filter if selected
        if selected_cleaner_id:
            try:
                selected_cleaner_profile = CleanerProfile.objects.get(id=selected_cleaner_id, business=business)
                payouts_queryset = payouts_queryset.filter(cleaner_profile=selected_cleaner_profile)
            except CleanerProfile.DoesNotExist:
                # If invalid cleaner_id, ignore the filter
                selected_cleaner_id = ''
        
        # Get all payouts with applied filters
        payouts = payouts_queryset.order_by('-created_at')
        
        # Get pending payouts (not yet paid)
        pending_payouts = payouts.filter(status='pending')
        
        # Get paid payouts
        paid_payouts = payouts.filter(status='paid')
        
        # Calculate total amounts
        total_amount = payouts.aggregate(Sum('amount'))['amount__sum'] or 0
        pending_amount = pending_payouts.aggregate(Sum('amount'))['amount__sum'] or 0
        paid_amount = paid_payouts.aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Get completed bookings that don't have payouts yet
        completed_bookings_without_payouts_query = Booking.objects.filter(
            business=business,
            isCompleted=True,
            cleaner__isnull=False
        ).exclude(
            payouts__isnull=False
        )
        
        # Apply cleaner filter to completed bookings if a cleaner is selected
        if selected_cleaner_profile:
            completed_bookings_without_payouts_query = completed_bookings_without_payouts_query.filter(
                cleaner=selected_cleaner_profile.cleaner
            )
            
        # Order the results
        completed_bookings_without_payouts = completed_bookings_without_payouts_query.order_by('-cleaningDate')
        
        context = {
            'is_business_owner': is_business_owner,
            'is_cleaner': is_cleaner,
            'business': business,
            'cleaner_profiles': cleaner_profiles,
            'payouts': payouts,
            'pending_payouts': pending_payouts,
            'paid_payouts': paid_payouts,
            'completed_bookings_without_payouts': completed_bookings_without_payouts,
            'payout_status_choices': PAYOUT_STATUS_CHOICES,
            'total_amount': total_amount,
            'pending_amount': pending_amount,
            'paid_amount': paid_amount,
            'selected_cleaner_id': selected_cleaner_id,
            'selected_cleaner_profile': selected_cleaner_profile,
        }
        
        return render(request, 'payouts/payouts_dashboard.html', context)
    
    elif is_cleaner:
        # Cleaner view - show only this cleaner's payouts
        cleaner_profile = CleanerProfile.objects.get(user=request.user)
        business = cleaner_profile.business
        cleaner = cleaner_profile.cleaner
        
        # Get all payouts for this cleaner profile
        payouts = CleanerPayout.objects.filter(
            cleaner_profile=cleaner_profile,
            business=business
        ).order_by('-created_at')
        
        # Calculate total amount from all payouts
        total_amount = payouts.aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Calculate pending amount from pending payouts
        pending_amount = payouts.filter(status='pending').aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Get completed bookings for this cleaner
        completed_bookings = Booking.objects.filter(
            business=business,
            cleaner=cleaner,
            isCompleted=True
        ).order_by('-cleaningDate')
        
        context = {
            'is_business_owner': is_business_owner,
            'is_cleaner': is_cleaner,
            'business': business,
            'cleaner': cleaner,
            'cleaner_profile': cleaner_profile,
            'payouts': payouts,
            'completed_bookings': completed_bookings,
            'total_amount': total_amount,
            'pending_amount': pending_amount,
        }
        
        return render(request, 'payouts/cleaner_payouts.html', context)
    
    else:
        # Neither a business owner nor a cleaner
        messages.error(request, "You don't have permission to access this page.")
        return redirect('home')


@login_required
def payout_detail(request, payout_id):
    """
    View details of a specific payout
    """
    # Check if user is a business owner
    is_business_owner = Business.objects.filter(user=request.user).exists()
    
    # Check if user is a cleaner
    is_cleaner = CleanerProfile.objects.filter(user=request.user).exists()
    
    if is_business_owner:
        business = Business.objects.get(user=request.user)
        payout = get_object_or_404(CleanerPayout, payout_id=payout_id, business=business)
    elif is_cleaner:
        cleaner_profile = CleanerProfile.objects.get(user=request.user)
        payout = get_object_or_404(CleanerPayout, payout_id=payout_id, cleaner_profile=cleaner_profile)
    else:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('home')
    
    # Get all bookings associated with this payout
    bookings = payout.bookings.all().order_by('-cleaningDate')
    
    context = {
        'is_business_owner': is_business_owner,
        'is_cleaner': is_cleaner,
        'payout': payout,
        'bookings': bookings,
        'payout_status_choices': PAYOUT_STATUS_CHOICES,
    }
    
    return render(request, 'payouts/payout_detail.html', context)


@login_required
@transaction.atomic
def create_payout(request):
    """
    Create a new payout for a cleaner
    """
    if not Business.objects.filter(user=request.user).exists():
        messages.error(request, "Only business owners can create payouts.")
        return redirect('home')
    
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('payouts_dashboard')
    
    business = Business.objects.get(user=request.user)
    
    # Get form data
    cleaner_profile_id = request.POST.get('cleaner_profile_id')
    booking_ids = request.POST.getlist('booking_ids')
    payment_method = request.POST.get('payment_method')
    notes = request.POST.get('notes')
    
    if not cleaner_profile_id or not booking_ids:
        messages.error(request, "Please select a cleaner and at least one booking.")
        return redirect('payouts_dashboard')
    
    try:
        cleaner_profile = CleanerProfile.objects.get(id=cleaner_profile_id, business=business)
        
        # Get all selected bookings
        bookings = Booking.objects.filter(
            id__in=booking_ids,
            business=business,
            cleaner=cleaner_profile.cleaner,
            isCompleted=True
        )
        
        if not bookings:
            messages.error(request, "No valid bookings selected.")
            return redirect('payouts_dashboard')
        
        # Calculate total payout amount
        total_amount = sum(booking.get_cleaner_payout() for booking in bookings)
        
        # Create the payout
        payout = CleanerPayout.objects.create(
            business=business,
            cleaner_profile=cleaner_profile,
            amount=total_amount,
            payment_method=payment_method,
            notes=notes
        )
        
        # Add bookings to the payout
        payout.bookings.set(bookings)
        
        messages.success(request, f"Payout created successfully for {cleaner_profile.cleaner.name}.")
        return redirect('payout_detail', payout_id=payout.payout_id)
        
    except Exception as e:
        messages.error(request, f"Error creating payout: {str(e)}")
        return redirect('payouts_dashboard')


@login_required
def mark_payout_as_paid(request, payout_id):
    """
    Mark a payout as paid
    """
    if not Business.objects.filter(user=request.user).exists():
        messages.error(request, "Only business owners can update payouts.")
        return redirect('home')
    
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('payouts_dashboard')
    
    business = Business.objects.get(user=request.user)
    payout = get_object_or_404(CleanerPayout, payout_id=payout_id, business=business)
    
    payment_method = request.POST.get('payment_method')
    payment_reference = request.POST.get('payment_reference')
    
    try:
        payout.mark_as_paid(payment_method, payment_reference)
        messages.success(request, f"Payout {payout.payout_id} marked as paid.")
    except Exception as e:
        messages.error(request, f"Error updating payout: {str(e)}")
    
    return redirect('payout_detail', payout_id=payout.payout_id)


@login_required
def cancel_payout(request, payout_id):
    """
    Cancel a payout
    """
    if not Business.objects.filter(user=request.user).exists():
        messages.error(request, "Only business owners can cancel payouts.")
        return redirect('home')
    
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('payouts_dashboard')
    
    business = Business.objects.get(user=request.user)
    payout = get_object_or_404(CleanerPayout, payout_id=payout_id, business=business)
    
    if payout.status == 'paid':
        messages.error(request, "Cannot cancel a payout that has already been paid.")
        return redirect('payout_detail', payout_id=payout.payout_id)
    
    try:
        payout.status = 'cancelled'
        payout.save()
        messages.success(request, f"Payout {payout.payout_id} has been cancelled.")
    except Exception as e:
        messages.error(request, f"Error cancelling payout: {str(e)}")
    
    return redirect('payout_detail', payout_id=payout.payout_id)
