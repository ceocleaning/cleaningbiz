from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q, F, Value, Avg
from django.db.models.functions import TruncMonth, TruncWeek, TruncDay, TruncYear, ExtractMonth
from invoice.models import Invoice, Payment
from bookings.models import Booking
from accounts.models import Business
from automation.models import Cleaners
from datetime import datetime, timedelta, date
from django.utils import timezone
import json
import calendar
from dateutil.relativedelta import relativedelta


@login_required
def analytics_dashboard(request):
    """Main analytics dashboard view"""
    if not request.user.business_set.first():
        return redirect('accounts:register_business')
        
    # Get basic metrics for the dashboard
    total_revenue = Invoice.objects.filter(
        booking__business__user=request.user,
        isPaid=True
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_invoices = Invoice.objects.filter(
        booking__business__user=request.user
    ).count()
    
    paid_invoices = Invoice.objects.filter(
        booking__business__user=request.user,
        isPaid=True
    ).count()
    
    # Calculate payment rate
    payment_rate = 0
    if total_invoices > 0:
        payment_rate = (paid_invoices / total_invoices) * 100
    
    # Get booking metrics
    total_bookings = Booking.objects.filter(
        business__user=request.user
    ).count()
    
    completed_bookings = Booking.objects.filter(
        business__user=request.user,
        isCompleted=True
    ).count()
    
    # Calculate completion rate
    completion_rate = 0
    if total_bookings > 0:
        completion_rate = (completed_bookings / total_bookings) * 100
    
    # Get cleaner metrics
    total_cleaners = Cleaners.objects.filter(
        business__user=request.user
    ).count()
    
    active_cleaners = Cleaners.objects.filter(
        business__user=request.user,
        isActive=True
    ).count()
    
    # Calculate cleaner utilization
    cleaner_utilization = 0
    if total_cleaners > 0:
        cleaner_utilization = (active_cleaners / total_cleaners) * 100
    
    context = {
        'total_revenue': total_revenue,
        'total_invoices': total_invoices,
        'paid_invoices': paid_invoices,
        'payment_rate': round(payment_rate, 1),
        'total_bookings': total_bookings,
        'completed_bookings': completed_bookings,
        'completion_rate': round(completion_rate, 1),
        'total_cleaners': total_cleaners,
        'active_cleaners': active_cleaners,
        'cleaner_utilization': round(cleaner_utilization, 1),
    }
    
    return render(request, 'analytics/dashboard.html', context)


@login_required
def revenue_data_api(request):
    """API endpoint for revenue trends data"""
    # Get time period from request (default to last 6 months)
    period = request.GET.get('period', 'monthly')
    months = int(request.GET.get('months', 6))
    
    # Calculate date range based on period
    end_date = timezone.now().date()
    
    if period == 'yearly':
        # For yearly, get data for the last 5 years
        years_to_show = 5
        start_date = date(end_date.year - years_to_show + 1, 1, 1)  # Start from Jan 1st of 5 years ago
    elif period == 'monthly':
        # For monthly, get data for the specified number of months
        start_date = end_date - relativedelta(months=months-1)  # Show last X months including current
        start_date = date(start_date.year, start_date.month, 1)  # Start from 1st of the month
    else:  # daily
        # For daily, get data for the last 30 days
        days_to_show = 30
        start_date = end_date - timedelta(days=days_to_show-1)  # Show last 30 days including today
    
    # Query invoices within date range
    invoices = Invoice.objects.filter(
        booking__business__user=request.user,
        createdAt__gte=start_date,
        createdAt__lte=end_date
    )
    
    # Create a complete list of time periods
    labels = []
    total_amounts = []
    paid_amounts = []
    pending_amounts = []
    total_counts = []
    paid_counts = []
    pending_counts = []
    
    if period == 'yearly':
        # Generate all years in range
        all_years = []
        for year in range(start_date.year, end_date.year + 1):
            all_years.append(date(year, 1, 1))
        
        # Group by year
        revenue_data = invoices.annotate(
            period=TruncYear('createdAt')
        ).values('period').annotate(
            total=Sum('amount'),
            count=Count('invoiceId'),
            paid_total=Sum('amount', filter=Q(isPaid=True)),
            paid_count=Count('invoiceId', filter=Q(isPaid=True))
        ).order_by('period')
        
        # Convert to dictionary for easier lookup
        revenue_dict = {item['period'].date(): item for item in revenue_data}
        
        # Fill in all years with data or zeros
        for year_date in all_years:
            labels.append(year_date.strftime('%Y'))
            
            if year_date in revenue_dict:
                total = revenue_dict[year_date]['total'] or 0
                paid = revenue_dict[year_date]['paid_total'] or 0
                pending = total - paid
                
                total_count = revenue_dict[year_date]['count'] or 0
                paid_count = revenue_dict[year_date]['paid_count'] or 0
                pending_count = total_count - paid_count
                
                total_amounts.append(total)
                paid_amounts.append(paid)
                pending_amounts.append(pending)
                
                total_counts.append(total_count)
                paid_counts.append(paid_count)
                pending_counts.append(pending_count)
            else:
                total_amounts.append(0)
                paid_amounts.append(0)
                pending_amounts.append(0)
                
                total_counts.append(0)
                paid_counts.append(0)
                pending_counts.append(0)
                
    elif period == 'monthly':
        # Generate all months in range
        all_months = []
        current_date = start_date
        while current_date <= end_date:
            all_months.append(current_date)
            current_date = current_date + relativedelta(months=1)
        
        # Group by month
        revenue_data = invoices.annotate(
            period=TruncMonth('createdAt')
        ).values('period').annotate(
            total=Sum('amount'),
            count=Count('invoiceId'),
            paid_total=Sum('amount', filter=Q(isPaid=True)),
            paid_count=Count('invoiceId', filter=Q(isPaid=True))
        ).order_by('period')
        
        # Convert to dictionary for easier lookup
        revenue_dict = {item['period'].date().replace(day=1): item for item in revenue_data}
        
        # Fill in all months with data or zeros
        for month_date in all_months:
            labels.append(month_date.strftime('%b %Y'))
            
            if month_date in revenue_dict:
                total = revenue_dict[month_date]['total'] or 0
                paid = revenue_dict[month_date]['paid_total'] or 0
                pending = total - paid
                
                total_count = revenue_dict[month_date]['count'] or 0
                paid_count = revenue_dict[month_date]['paid_count'] or 0
                pending_count = total_count - paid_count
                
                total_amounts.append(total)
                paid_amounts.append(paid)
                pending_amounts.append(pending)
                
                total_counts.append(total_count)
                paid_counts.append(paid_count)
                pending_counts.append(pending_count)
            else:
                total_amounts.append(0)
                paid_amounts.append(0)
                pending_amounts.append(0)
                
                total_counts.append(0)
                paid_counts.append(0)
                pending_counts.append(0)
    else:
        # Generate all days in range
        all_days = []
        current_date = start_date
        while current_date <= end_date:
            all_days.append(current_date)
            current_date = current_date + timedelta(days=1)
        
        # Group by day
        revenue_data = invoices.annotate(
            period=TruncDay('createdAt')
        ).values('period').annotate(
            total=Sum('amount'),
            count=Count('invoiceId'),
            paid_total=Sum('amount', filter=Q(isPaid=True)),
            paid_count=Count('invoiceId', filter=Q(isPaid=True))
        ).order_by('period')
        
        # Convert to dictionary for easier lookup
        revenue_dict = {item['period'].date(): item for item in revenue_data}
        
        # Fill in all days with data or zeros
        for day_date in all_days:
            labels.append(day_date.strftime('%d %b'))
            
            if day_date in revenue_dict:
                total = revenue_dict[day_date]['total'] or 0
                paid = revenue_dict[day_date]['paid_total'] or 0
                pending = total - paid
                
                total_count = revenue_dict[day_date]['count'] or 0
                paid_count = revenue_dict[day_date]['paid_count'] or 0
                pending_count = total_count - paid_count
                
                total_amounts.append(total)
                paid_amounts.append(paid)
                pending_amounts.append(pending)
                
                total_counts.append(total_count)
                paid_counts.append(paid_count)
                pending_counts.append(pending_count)
            else:
                total_amounts.append(0)
                paid_amounts.append(0)
                pending_amounts.append(0)
                
                total_counts.append(0)
                paid_counts.append(0)
                pending_counts.append(0)
    
    # Return JSON response
    return JsonResponse({
        'labels': labels,
        'datasets': [
            {
                'label': 'Total Revenue',
                'data': total_amounts,
                'backgroundColor': 'rgba(54, 162, 235, 0.6)',
                'borderColor': 'rgba(54, 162, 235, 1)',
                'borderWidth': 1,
                'invoice_counts': total_counts
            },
            {
                'label': 'Paid Revenue',
                'data': paid_amounts,
                'backgroundColor': 'rgba(75, 192, 92, 0.6)',
                'borderColor': 'rgba(75, 192, 92, 1)',
                'borderWidth': 1,
                'invoice_counts': paid_counts
            },
            {
                'label': 'Pending Revenue',
                'data': pending_amounts,
                'backgroundColor': 'rgba(255, 193, 7, 0.6)',
                'borderColor': 'rgba(255, 193, 7, 1)',
                'borderWidth': 1,
                'invoice_counts': pending_counts
            }
        ]
    })


@login_required
def booking_data_api(request):
    """API endpoint for booking trends data"""
    # Get time period from request (default to last 6 months)
    period = request.GET.get('period', 'monthly')
    months = int(request.GET.get('months', 6))
    chart_type = request.GET.get('chart_type', 'trend')  # trend or status
    
    # Calculate date range based on period
    end_date = timezone.now().date()
    
    if period == 'yearly':
        # For yearly, get data for the last 5 years
        years_to_show = 5
        start_date = date(end_date.year - years_to_show + 1, 1, 1)  # Start from Jan 1st of 5 years ago
    elif period == 'monthly':
        # For monthly, get data for the specified number of months
        start_date = end_date - relativedelta(months=months-1)  # Show last X months including current
        start_date = date(start_date.year, start_date.month, 1)  # Start from 1st of the month
    else:  # daily
        # For daily, get data for the last 30 days
        days_to_show = 30
        start_date = end_date - timedelta(days=days_to_show-1)  # Show last 30 days including today
    
    # Query bookings within date range
    bookings = Booking.objects.filter(
        business__user=request.user,
        createdAt__gte=start_date,
        createdAt__lte=end_date
    )
    
    if chart_type == 'trend':
        # Create a complete list of time periods for trend chart
        labels = []
        total_bookings = []
        completed_bookings = []
        pending_bookings = []
        
        if period == 'yearly':
            # Generate all years in range
            all_years = []
            for year in range(start_date.year, end_date.year + 1):
                all_years.append(date(year, 1, 1))
            
            # Group by year
            booking_data = bookings.annotate(
                period=TruncYear('createdAt')
            ).values('period').annotate(
                total=Count('bookingId'),
                completed=Count('bookingId', filter=Q(isCompleted=True)),
                pending=Count('bookingId', filter=Q(isCompleted=False))
            ).order_by('period')
            
            # Convert to dictionary for easier lookup
            booking_dict = {item['period'].date(): item for item in booking_data}
            
            # Fill in all years with data or zeros
            for year_date in all_years:
                labels.append(year_date.strftime('%Y'))
                
                if year_date in booking_dict:
                    total_bookings.append(booking_dict[year_date]['total'] or 0)
                    completed_bookings.append(booking_dict[year_date]['completed'] or 0)
                    pending_bookings.append(booking_dict[year_date]['pending'] or 0)
                else:
                    total_bookings.append(0)
                    completed_bookings.append(0)
                    pending_bookings.append(0)
                    
        elif period == 'monthly':
            # Generate all months in range
            all_months = []
            current_date = start_date
            while current_date <= end_date:
                all_months.append(current_date)
                current_date = current_date + relativedelta(months=1)
            
            # Group by month
            booking_data = bookings.annotate(
                period=TruncMonth('createdAt')
            ).values('period').annotate(
                total=Count('bookingId'),
                completed=Count('bookingId', filter=Q(isCompleted=True)),
                pending=Count('bookingId', filter=Q(isCompleted=False))
            ).order_by('period')
            
            # Convert to dictionary for easier lookup
            booking_dict = {item['period'].date().replace(day=1): item for item in booking_data}
            
            # Fill in all months with data or zeros
            for month_date in all_months:
                labels.append(month_date.strftime('%b %Y'))
                
                if month_date in booking_dict:
                    total_bookings.append(booking_dict[month_date]['total'] or 0)
                    completed_bookings.append(booking_dict[month_date]['completed'] or 0)
                    pending_bookings.append(booking_dict[month_date]['pending'] or 0)
                else:
                    total_bookings.append(0)
                    completed_bookings.append(0)
                    pending_bookings.append(0)
        else:
            # Generate all days in range
            all_days = []
            current_date = start_date
            while current_date <= end_date:
                all_days.append(current_date)
                current_date = current_date + timedelta(days=1)
            
            # Group by day
            booking_data = bookings.annotate(
                period=TruncDay('createdAt')
            ).values('period').annotate(
                total=Count('bookingId'),
                completed=Count('bookingId', filter=Q(isCompleted=True)),
                pending=Count('bookingId', filter=Q(isCompleted=False))
            ).order_by('period')
            
            # Convert to dictionary for easier lookup
            booking_dict = {item['period'].date(): item for item in booking_data}
            
            # Fill in all days with data or zeros
            for day_date in all_days:
                labels.append(day_date.strftime('%d %b'))
                
                if day_date in booking_dict:
                    total_bookings.append(booking_dict[day_date]['total'] or 0)
                    completed_bookings.append(booking_dict[day_date]['completed'] or 0)
                    pending_bookings.append(booking_dict[day_date]['pending'] or 0)
                else:
                    total_bookings.append(0)
                    completed_bookings.append(0)
                    pending_bookings.append(0)
        
        # Return JSON response for trend chart
        return JsonResponse({
            'labels': labels,
            'datasets': [
                {
                    'label': 'Total Bookings',
                    'data': total_bookings,
                    'backgroundColor': 'rgba(54, 162, 235, 0.6)',
                    'borderColor': 'rgba(54, 162, 235, 1)',
                    'borderWidth': 1
                },
                {
                    'label': 'Completed Bookings',
                    'data': completed_bookings,
                    'backgroundColor': 'rgba(75, 192, 92, 0.6)',
                    'borderColor': 'rgba(75, 192, 92, 1)',
                    'borderWidth': 1
                },
                {
                    'label': 'Pending Bookings',
                    'data': pending_bookings,
                    'backgroundColor': 'rgba(255, 193, 7, 0.6)',
                    'borderColor': 'rgba(255, 193, 7, 1)',
                    'borderWidth': 1
                }
            ]
        })
    else:
        # Service Type distribution chart (pie/doughnut chart)
        # Count bookings by service type
        service_data = bookings.values('serviceType').annotate(count=Count('bookingId')).order_by('serviceType')
        
        # Prepare data for chart
        labels = []
        data = []
        background_colors = []
        border_colors = []
        
        # Color mapping for different service types
        service_colors = {
            'standard': ['rgba(54, 162, 235, 0.6)', 'rgba(54, 162, 235, 1)'],     # Blue
            'deep': ['rgba(75, 192, 92, 0.6)', 'rgba(75, 192, 92, 1)'],              # Green
            'moveinmoveout': ['rgba(255, 159, 64, 0.6)', 'rgba(255, 159, 64, 1)'],   # Orange
            'airbnb': ['rgba(153, 102, 255, 0.6)', 'rgba(153, 102, 255, 1)'],        # Purple
        }
        
        # Service type display names
        service_display_names = {
            'standard': 'Standard Cleaning',
            'deep': 'Deep Cleaning',
            'moveinmoveout': 'Move In/Move Out',
            'airbnb': 'Airbnb Cleaning',
            None: 'Not Specified'
        }
        
        for item in service_data:
            service_type = item['serviceType']
            count = item['count']
            
            # Get display name for service type
            display_name = service_display_names.get(service_type, 'Other')
            
            labels.append(display_name)
            data.append(count)
            
            # Get colors for this service type or use default gray
            colors = service_colors.get(service_type, ['rgba(108, 117, 125, 0.6)', 'rgba(108, 117, 125, 1)'])
            background_colors.append(colors[0])
            border_colors.append(colors[1])
        
        # Return JSON response for service type chart
        return JsonResponse({
            'labels': labels,
            'datasets': [{
                'data': data,
                'backgroundColor': background_colors,
                'borderColor': border_colors,
                'borderWidth': 1
            }]
        })


@login_required
def cleaner_data_api(request):
    """API endpoint for cleaner analytics data"""
    # Get time period from request (default to last 6 months)
    period = request.GET.get('period', 'monthly')
    months = int(request.GET.get('months', 6))
    chart_type = request.GET.get('chart_type', 'bookings')  # bookings, performance, revenue, service_types, or detailed
    
    # Calculate date range based on period
    end_date = timezone.now().date()
    
    if period == 'yearly':
        # For yearly, get data for the last 5 years
        years_to_show = 5
        start_date = date(end_date.year - years_to_show + 1, 1, 1)  # Start from Jan 1st of 5 years ago
    elif period == 'monthly':
        # For monthly, get data for the specified number of months
        start_date = end_date - relativedelta(months=months-1)  # Show last X months including current
        start_date = date(start_date.year, start_date.month, 1)  # Start from 1st of the month
    else:  # daily
        # For daily, get data for the last 30 days
        days_to_show = 30
        start_date = end_date - timedelta(days=days_to_show-1)  # Show last 30 days including today
    
    # Get all cleaners for this business
    cleaners = Cleaners.objects.filter(
        business__user=request.user
    )
    
    if chart_type == 'bookings':
        # Get bookings assigned to each cleaner
        cleaner_bookings = []
        cleaner_names = []
        cleaner_colors = []
        
        # Color palette for cleaners
        color_palette = [
            ['rgba(54, 162, 235, 0.6)', 'rgba(54, 162, 235, 1)'],   # Blue
            ['rgba(75, 192, 92, 0.6)', 'rgba(75, 192, 92, 1)'],       # Green
            ['rgba(255, 159, 64, 0.6)', 'rgba(255, 159, 64, 1)'],     # Orange
            ['rgba(153, 102, 255, 0.6)', 'rgba(153, 102, 255, 1)'],   # Purple
            ['rgba(255, 99, 132, 0.6)', 'rgba(255, 99, 132, 1)'],     # Red
            ['rgba(255, 205, 86, 0.6)', 'rgba(255, 205, 86, 1)'],     # Yellow
            ['rgba(201, 203, 207, 0.6)', 'rgba(201, 203, 207, 1)'],   # Gray
            ['rgba(0, 204, 150, 0.6)', 'rgba(0, 204, 150, 1)'],       # Teal
        ]
        
        # Get bookings count for each cleaner
        for i, cleaner in enumerate(cleaners):
            booking_count = Booking.objects.filter(
                business__user=request.user,
                cleaner=cleaner,
                createdAt__gte=start_date,
                createdAt__lte=end_date
            ).count()
            
            cleaner_bookings.append(booking_count)
            cleaner_names.append(cleaner.name)
            
            # Assign color from palette (cycle through if more cleaners than colors)
            color_index = i % len(color_palette)
            cleaner_colors.append(color_palette[color_index][0])
        
        # Return JSON response for cleaner bookings chart
        return JsonResponse({
            'labels': cleaner_names,
            'datasets': [{
                'data': cleaner_bookings,
                'backgroundColor': cleaner_colors,
                'borderWidth': 1
            }]
        })
    
    elif chart_type == 'performance':
        # For each cleaner, calculate:
        # 1. Average bookings per month
        # 2. Completion rate (completed bookings / total bookings)
        # 3. Average square footage handled
        # 4. Average service time (if available)
        
        cleaner_data = []
        
        for cleaner in cleaners:
            # Get all bookings for this cleaner in the date range
            cleaner_bookings = Booking.objects.filter(
                business__user=request.user,
                cleaner=cleaner,
                createdAt__gte=start_date,
                createdAt__lte=end_date
            )
            
            total_bookings = cleaner_bookings.count()
            completed_bookings = cleaner_bookings.filter(isCompleted=True).count()
            
            # Calculate completion rate
            completion_rate = 0
            if total_bookings > 0:
                completion_rate = (completed_bookings / total_bookings) * 100
            
            # Calculate months in the date range
            if period == 'yearly':
                months_in_range = (end_date.year - start_date.year) * 12
            elif period == 'monthly':
                months_in_range = months
            else:  # daily
                months_in_range = 1  # For daily view, just use 1 month to get bookings per month
            
            # Calculate average bookings per month
            avg_bookings_per_month = 0
            if months_in_range > 0:
                avg_bookings_per_month = total_bookings / months_in_range
            
            # Calculate average square footage
            avg_square_footage = cleaner_bookings.aggregate(avg=Avg('squareFeet'))['avg'] or 0
            
            # Calculate average number of bedrooms and bathrooms
            avg_bedrooms = cleaner_bookings.aggregate(avg=Avg('bedrooms'))['avg'] or 0
            avg_bathrooms = cleaner_bookings.aggregate(avg=Avg('bathrooms'))['avg'] or 0
            
            cleaner_data.append({
                'name': cleaner.name,
                'total_bookings': total_bookings,
                'completed_bookings': completed_bookings,
                'completion_rate': round(completion_rate, 1),
                'avg_bookings_per_month': round(avg_bookings_per_month, 1),
                'avg_square_footage': round(avg_square_footage, 1),
                'avg_bedrooms': round(avg_bedrooms, 1),
                'avg_bathrooms': round(avg_bathrooms, 1)
            })
        
        # Sort by total bookings (descending)
        cleaner_data.sort(key=lambda x: x['total_bookings'], reverse=True)
        
        # Prepare data for chart
        cleaner_names = [item['name'] for item in cleaner_data]
        completion_rates = [item['completion_rate'] for item in cleaner_data]
        avg_bookings = [item['avg_bookings_per_month'] for item in cleaner_data]
        
        # Return JSON response for cleaner performance chart
        return JsonResponse({
            'labels': cleaner_names,
            'datasets': [
                {
                    'label': 'Completion Rate (%)',
                    'data': completion_rates,
                    'backgroundColor': 'rgba(75, 192, 92, 0.6)',
                    'borderColor': 'rgba(75, 192, 92, 1)',
                    'borderWidth': 1,
                    'yAxisID': 'y'
                },
                {
                    'label': 'Avg. Bookings/Month',
                    'data': avg_bookings,
                    'backgroundColor': 'rgba(54, 162, 235, 0.6)',
                    'borderColor': 'rgba(54, 162, 235, 1)',
                    'borderWidth': 1,
                    'yAxisID': 'y1'
                }
            ],
            'detailed_data': cleaner_data
        })
    
    elif chart_type == 'revenue':
        # For each cleaner, analyze revenue
        labels = []
        total_revenue_data = []
        paid_revenue_data = []
        pending_revenue_data = []
        
        for cleaner in cleaners:
            # Get all bookings for this cleaner in the date range
            cleaner_bookings = Booking.objects.filter(
                business__user=request.user,
                cleaner=cleaner,
                createdAt__gte=start_date,
                createdAt__lte=end_date
            )
            
            # Skip cleaners with no bookings
            if cleaner_bookings.count() == 0:
                continue
            
            # Get total revenue
            total_revenue = cleaner_bookings.aggregate(total=Sum('totalPrice'))['total'] or 0
            
            # Get paid revenue (from invoices related to these bookings)
            booking_ids = cleaner_bookings.values_list('id', flat=True)
            paid_revenue = Invoice.objects.filter(
                booking__id__in=booking_ids,
                isPaid=True
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Get pending revenue (total minus paid)
            pending_revenue = float(total_revenue) - float(paid_revenue)
            if pending_revenue < 0:
                pending_revenue = 0  # Ensure we don't have negative pending revenue
            
            # Add to datasets
            labels.append(cleaner.name)
            total_revenue_data.append(float(total_revenue))
            paid_revenue_data.append(float(paid_revenue))
            pending_revenue_data.append(float(pending_revenue))
        
        # Create datasets for Chart.js
        datasets = [
            {
                'label': 'Total Revenue',
                'data': total_revenue_data,
                'backgroundColor': 'rgba(54, 162, 235, 0.5)',
                'borderColor': 'rgba(54, 162, 235, 1)',
                'borderWidth': 1
            },
            {
                'label': 'Paid Revenue',
                'data': paid_revenue_data,
                'backgroundColor': 'rgba(75, 192, 192, 0.5)',
                'borderColor': 'rgba(75, 192, 192, 1)',
                'borderWidth': 1
            },
            {
                'label': 'Pending Revenue',
                'data': pending_revenue_data,
                'backgroundColor': 'rgba(255, 159, 64, 0.5)',
                'borderColor': 'rgba(255, 159, 64, 1)',
                'borderWidth': 1
            }
        ]
        
        return JsonResponse({
            'labels': labels,
            'datasets': datasets
        })
    
    elif chart_type == 'service_types':
        # For each cleaner, analyze what service types they handle most
        service_type_data = []
        
        # Service type display names
        service_display_names = {
            'standard': 'Standard Cleaning',
            'deep': 'Deep Cleaning',
            'moveinmoveout': 'Move In/Move Out',
            'airbnb': 'Airbnb Cleaning',
            None: 'Not Specified'
        }
        
        for cleaner in cleaners:
            # Get service type distribution for this cleaner
            cleaner_service_types = Booking.objects.filter(
                business__user=request.user,
                cleaner=cleaner,
                createdAt__gte=start_date,
                createdAt__lte=end_date
            ).values('serviceType').annotate(count=Count('id')).order_by('-count')
            
            # Get total bookings for this cleaner
            total_cleaner_bookings = Booking.objects.filter(
                business__user=request.user,
                cleaner=cleaner,
                createdAt__gte=start_date,
                createdAt__lte=end_date
            ).count()
            
            # Format service type data
            service_types = []
            for service in cleaner_service_types:
                service_type = service['serviceType']
                count = service['count']
                percentage = 0
                if total_cleaner_bookings > 0:
                    percentage = (count / total_cleaner_bookings) * 100
                
                service_types.append({
                    'type': service_display_names.get(service_type, 'Other'),
                    'count': count,
                    'percentage': round(percentage, 1)
                })
            
            service_type_data.append({
                'name': cleaner.name,
                'service_types': service_types,
                'total_bookings': total_cleaner_bookings
            })
        
        # Sort by total bookings (descending)
        service_type_data.sort(key=lambda x: x['total_bookings'], reverse=True)
        
        return JsonResponse({
            'cleaner_service_data': service_type_data
        })
    
    else:  # detailed table data
        # Provide detailed data for all cleaners
        detailed_data = []
        
        # Service type display names
        service_display_names = {
            'standard': 'Standard Cleaning',
            'deep': 'Deep Cleaning',
            'moveinmoveout': 'Move In/Move Out',
            'airbnb': 'Airbnb Cleaning',
            None: 'Not Specified'
        }
        
        for cleaner in cleaners:
            # Get all bookings for this cleaner in the date range
            cleaner_bookings = Booking.objects.filter(
                business__user=request.user,
                cleaner=cleaner,
                createdAt__gte=start_date,
                createdAt__lte=end_date
            )
            
            total_bookings = cleaner_bookings.count()
            completed_bookings = cleaner_bookings.filter(isCompleted=True).count()
            
            # Skip cleaners with no bookings
            if total_bookings == 0:
                continue
            
            # Calculate completion rate
            completion_rate = 0
            if total_bookings > 0:
                completion_rate = (completed_bookings / total_bookings) * 100
            
            # Get total revenue from these bookings
            total_revenue = cleaner_bookings.aggregate(total=Sum('totalPrice'))['total'] or 0
            
            # Get paid revenue (from invoices related to these bookings)
            booking_ids = cleaner_bookings.values_list('id', flat=True)
            paid_revenue = Invoice.objects.filter(
                booking__id__in=booking_ids,
                isPaid=True
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Get pending revenue (total minus paid)
            pending_revenue = float(total_revenue) - float(paid_revenue)
            if pending_revenue < 0:
                pending_revenue = 0  # Ensure we don't have negative pending revenue
            
            # Calculate average metrics
            avg_square_footage = cleaner_bookings.aggregate(avg=Avg('squareFeet'))['avg'] or 0
            avg_bedrooms = cleaner_bookings.aggregate(avg=Avg('bedrooms'))['avg'] or 0
            avg_bathrooms = cleaner_bookings.aggregate(avg=Avg('bathrooms'))['avg'] or 0
            
            # Calculate average bookings per month
            months_in_range = max(1, (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1)
            avg_bookings_per_month = total_bookings / months_in_range
            
            # Get service type distribution
            service_type_counts = cleaner_bookings.values('serviceType').annotate(count=Count('id'))
            service_types = []
            for service in service_type_counts:
                service_type = service['serviceType']
                count = service['count']
                percentage = 0
                if total_bookings > 0:
                    percentage = (count / total_bookings) * 100
                
                service_types.append({
                    'type': service_display_names.get(service_type, 'Other'),
                    'count': count,
                    'percentage': round(percentage, 1)
                })
            
            # Add to detailed data
            detailed_data.append({
                'name': cleaner.name,
                'total_bookings': total_bookings,
                'completed_bookings': completed_bookings,
                'completion_rate': round(completion_rate, 1),
                'total_revenue': float(total_revenue),
                'paid_revenue': float(paid_revenue),
                'pending_revenue': float(pending_revenue),
                'avg_revenue_per_booking': float(total_revenue / total_bookings) if total_bookings > 0 else 0,
                'avg_square_footage': round(avg_square_footage, 1),
                'avg_bedrooms': round(avg_bedrooms, 1),
                'avg_bathrooms': round(avg_bathrooms, 1),
                'avg_bookings_per_month': round(avg_bookings_per_month, 1),
                'service_types': service_types
            })
        
        # Sort by total bookings (descending)
        detailed_data.sort(key=lambda x: x['total_bookings'], reverse=True)
        
        # Also include the cleaner names as labels for charts
        cleaner_labels = [cleaner['name'] for cleaner in detailed_data]
        
        return JsonResponse({
            'labels': cleaner_labels,
            'detailed_data': detailed_data
        })


@login_required
def customer_data_api(request):
    """API endpoint for customer analytics data"""
    # Get time period from request (default to last 6 months)
    period = request.GET.get('period', 'monthly')
    months = int(request.GET.get('months', 6))
    
    # Calculate date range based on period
    end_date = timezone.now().date()
    
    if period == 'yearly':
        # For yearly, get data for the last 5 years
        years_to_show = 5
        start_date = date(end_date.year - years_to_show + 1, 1, 1)  # Start from Jan 1st of 5 years ago
    elif period == 'monthly':
        # For monthly, get data for the specified number of months
        start_date = end_date - relativedelta(months=months-1)  # Show last X months including current
        start_date = date(start_date.year, start_date.month, 1)  # Start from 1st of the month
    else:  # daily
        # For daily, get data for the last 30 days
        days_to_show = 30
        start_date = end_date - timedelta(days=days_to_show-1)  # Show last 30 days including today
    
    # Get all bookings for this business in the date range
    bookings = Booking.objects.filter(
        business__user=request.user,
        createdAt__gte=start_date,
        createdAt__lte=end_date
    )
    
    # Get total number of bookings
    total_bookings = bookings.count()
    
    # Group bookings by customer email to find repeat customers
    customer_bookings = {}
    for booking in bookings:
        if not booking.email:  # Skip bookings without email
            continue
            
        email = booking.email.lower()  # Normalize email to lowercase
        if email in customer_bookings:
            customer_bookings[email]['count'] += 1
            customer_bookings[email]['total_spent'] += float(booking.totalPrice or 0)
            customer_bookings[email]['last_booking'] = max(customer_bookings[email]['last_booking'], booking.createdAt)
        else:
            customer_bookings[email] = {
                'email': email,
                'name': f"{booking.firstName or ''} {booking.lastName or ''}".strip(),
                'count': 1,
                'total_spent': float(booking.totalPrice or 0),
                'first_booking': booking.createdAt,
                'last_booking': booking.createdAt,
                'phone': booking.phoneNumber
            }
    
    # Calculate customer metrics
    unique_customers = len(customer_bookings)
    repeat_customers = sum(1 for email, data in customer_bookings.items() if data['count'] > 1)
    repeat_customer_percentage = (repeat_customers / unique_customers * 100) if unique_customers > 0 else 0
    
    # Convert customer_bookings dictionary to a list for the response
    customer_list = list(customer_bookings.values())
    
    # Sort by booking count (descending)
    customer_list.sort(key=lambda x: x['count'], reverse=True)
    
    # Format dates for JSON serialization
    for customer in customer_list:
        customer['first_booking'] = customer['first_booking'].strftime('%Y-%m-%d')
        customer['last_booking'] = customer['last_booking'].strftime('%Y-%m-%d')
    
    # Prepare data for charts
    booking_distribution = [
        {'label': '1 Booking', 'count': sum(1 for c in customer_list if c['count'] == 1)},
        {'label': '2-3 Bookings', 'count': sum(1 for c in customer_list if 2 <= c['count'] <= 3)},
        {'label': '4-6 Bookings', 'count': sum(1 for c in customer_list if 4 <= c['count'] <= 6)},
        {'label': '7+ Bookings', 'count': sum(1 for c in customer_list if c['count'] >= 7)}
    ]
    
    return JsonResponse({
        'customer_list': customer_list,
        'metrics': {
            'total_bookings': total_bookings,
            'unique_customers': unique_customers,
            'repeat_customers': repeat_customers,
            'repeat_customer_percentage': round(repeat_customer_percentage, 1)
        },
        'booking_distribution': booking_distribution
    })


@login_required
def addon_data_api(request):
    """API endpoint for addon analytics data"""
    # Get time period from request (default to last 6 months)
    period = request.GET.get('period', 'monthly')
    months = int(request.GET.get('months', 6))
    
    # Calculate date range based on period
    end_date = timezone.now().date()
    
    if period == 'yearly':
        # For yearly, get data for the last 5 years
        years_to_show = 5
        start_date = date(end_date.year - years_to_show + 1, 1, 1)  # Start from Jan 1st of 5 years ago
    elif period == 'monthly':
        # For monthly, get data for the specified number of months
        start_date = end_date - relativedelta(months=months-1)  # Show last X months including current
        start_date = date(start_date.year, start_date.month, 1)  # Start from 1st of the month
    else:  # daily
        # For daily, get data for the last 30 days
        days_to_show = 30
        start_date = end_date - timedelta(days=days_to_show-1)  # Show last 30 days including today
    
    # Get all bookings for this business in the date range
    bookings = Booking.objects.filter(
        business__user=request.user,
        createdAt__gte=start_date,
        createdAt__lte=end_date
    )
    
    # Initialize addon counters and revenue
    addon_counts = {
        'dishes': {'count': 0, 'revenue': 0, 'name': 'Dishes'},
        'laundry': {'count': 0, 'revenue': 0, 'name': 'Laundry'},
        'window': {'count': 0, 'revenue': 0, 'name': 'Window Cleaning'},
        'pets': {'count': 0, 'revenue': 0, 'name': 'Pets Cleaning'},
        'fridge': {'count': 0, 'revenue': 0, 'name': 'Fridge Cleaning'},
        'oven': {'count': 0, 'revenue': 0, 'name': 'Oven Cleaning'},
        'baseboard': {'count': 0, 'revenue': 0, 'name': 'Baseboard'},
        'blinds': {'count': 0, 'revenue': 0, 'name': 'Blinds'},
        'green': {'count': 0, 'revenue': 0, 'name': 'Green Cleaning'},
        'cabinets': {'count': 0, 'revenue': 0, 'name': 'Cabinets Cleaning'},
        'patio': {'count': 0, 'revenue': 0, 'name': 'Patio Sweeping'},
        'garage': {'count': 0, 'revenue': 0, 'name': 'Garage Sweeping'},
    }
    
    # Get business settings to find addon prices
    try:
        business = Business.objects.get(user=request.user)
        settings = business.settings
        
        # Get addon prices from settings
        addon_prices = {
            'dishes': float(settings.addonPriceDishes or 0),
            'laundry': float(settings.addonPriceLaundry or 0),
            'window': float(settings.addonPriceWindow or 0),
            'pets': float(settings.addonPricePets or 0),
            'fridge': float(settings.addonPriceFridge or 0),
            'oven': float(settings.addonPriceOven or 0),
            'baseboard': float(settings.addonPriceBaseboard or 0),
            'blinds': float(settings.addonPriceBlinds or 0),
            'green': float(settings.addonPriceGreen or 0),
            'cabinets': float(settings.addonPriceCabinets or 0),
            'patio': float(settings.addonPricePatio or 0),
            'garage': float(settings.addonPriceGarage or 0),
        }
    except (Business.DoesNotExist, AttributeError):
        addon_prices = {key: 0 for key in addon_counts.keys()}
    
    # Custom addons data
    custom_addons = {}
    
    # Process bookings to count addons and calculate revenue
    for booking in bookings:
        # Standard addons
        if booking.addonDishes and booking.addonDishes > 0:
            addon_counts['dishes']['count'] += booking.addonDishes
            addon_counts['dishes']['revenue'] += booking.addonDishes * addon_prices['dishes']
            
        if booking.addonLaundryLoads and booking.addonLaundryLoads > 0:
            addon_counts['laundry']['count'] += booking.addonLaundryLoads
            addon_counts['laundry']['revenue'] += booking.addonLaundryLoads * addon_prices['laundry']
            
        if booking.addonWindowCleaning and booking.addonWindowCleaning > 0:
            addon_counts['window']['count'] += booking.addonWindowCleaning
            addon_counts['window']['revenue'] += booking.addonWindowCleaning * addon_prices['window']
            
        if booking.addonPetsCleaning and booking.addonPetsCleaning > 0:
            addon_counts['pets']['count'] += booking.addonPetsCleaning
            addon_counts['pets']['revenue'] += booking.addonPetsCleaning * addon_prices['pets']
            
        if booking.addonFridgeCleaning and booking.addonFridgeCleaning > 0:
            addon_counts['fridge']['count'] += booking.addonFridgeCleaning
            addon_counts['fridge']['revenue'] += booking.addonFridgeCleaning * addon_prices['fridge']
            
        if booking.addonOvenCleaning and booking.addonOvenCleaning > 0:
            addon_counts['oven']['count'] += booking.addonOvenCleaning
            addon_counts['oven']['revenue'] += booking.addonOvenCleaning * addon_prices['oven']
            
        if booking.addonBaseboard and booking.addonBaseboard > 0:
            addon_counts['baseboard']['count'] += booking.addonBaseboard
            addon_counts['baseboard']['revenue'] += booking.addonBaseboard * addon_prices['baseboard']
            
        if booking.addonBlinds and booking.addonBlinds > 0:
            addon_counts['blinds']['count'] += booking.addonBlinds
            addon_counts['blinds']['revenue'] += booking.addonBlinds * addon_prices['blinds']
            
        if booking.addonGreenCleaning and booking.addonGreenCleaning > 0:
            addon_counts['green']['count'] += booking.addonGreenCleaning
            addon_counts['green']['revenue'] += booking.addonGreenCleaning * addon_prices['green']
            
        if booking.addonCabinetsCleaning and booking.addonCabinetsCleaning > 0:
            addon_counts['cabinets']['count'] += booking.addonCabinetsCleaning
            addon_counts['cabinets']['revenue'] += booking.addonCabinetsCleaning * addon_prices['cabinets']
            
        if booking.addonPatioSweeping and booking.addonPatioSweeping > 0:
            addon_counts['patio']['count'] += booking.addonPatioSweeping
            addon_counts['patio']['revenue'] += booking.addonPatioSweeping * addon_prices['patio']
            
        if booking.addonGarageSweeping and booking.addonGarageSweeping > 0:
            addon_counts['garage']['count'] += booking.addonGarageSweeping
            addon_counts['garage']['revenue'] += booking.addonGarageSweeping * addon_prices['garage']
        
        # Custom addons
        try:
            for custom_addon in booking.customAddons.all():
                try:
                    addon_name = custom_addon.addon.addonName
                    addon_price = float(custom_addon.addon.addonPrice or 0)
                    addon_qty = custom_addon.qty or 0
                    
                    if addon_name in custom_addons:
                        custom_addons[addon_name]['count'] += addon_qty
                        custom_addons[addon_name]['revenue'] += addon_qty * addon_price
                    else:
                        custom_addons[addon_name] = {
                            'count': addon_qty,
                            'revenue': addon_qty * addon_price,
                            'name': addon_name,
                            'is_custom': True
                        }
                except (AttributeError, TypeError):
                    # Skip this custom addon if there's an issue accessing its properties
                    continue
        except (AttributeError, TypeError):
            # Skip custom addons for this booking if there's an issue
            pass
    
    # Filter out addons with zero count
    standard_addons = [addon for addon in addon_counts.values() if addon['count'] > 0]
    custom_addon_list = list(custom_addons.values())
    
    # Combine standard and custom addons
    all_addons = standard_addons + custom_addon_list
    
    # Sort addons by count (for pie chart)
    addons_by_count = sorted(all_addons, key=lambda x: x['count'], reverse=True)
    
    # Sort addons by revenue (for table)
    addons_by_revenue = sorted(all_addons, key=lambda x: x['revenue'], reverse=True)
    
    # Prepare data for pie chart
    pie_chart_data = {
        'labels': [addon['name'] for addon in addons_by_count],
        'data': [addon['count'] for addon in addons_by_count]
    }
    
    # Calculate total revenue from addons
    total_addon_revenue = sum(addon['revenue'] for addon in all_addons)
    
    # Calculate percentage of total revenue for each addon
    for addon in addons_by_revenue:
        if total_addon_revenue > 0:
            addon['percentage'] = round((addon['revenue'] / total_addon_revenue) * 100, 1)
        else:
            addon['percentage'] = 0
    
    return JsonResponse({
        'pie_chart': pie_chart_data,
        'addons_by_revenue': addons_by_revenue,
        'total_addon_revenue': total_addon_revenue
    })
