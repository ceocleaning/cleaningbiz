from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.paginator import Paginator
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification
from .services import NotificationService
from .utils import get_user_type

from django.db.models import Q

# Web views for notifications
@login_required
def notification_list(request):
    """View to display user's notifications"""
    
    # Base query - filter by recipient
    notifications = Notification.objects.filter(Q(recipient=request.user) | Q(email_to=request.user.email))
    

    
    # Paginate results
    paginator = Paginator(notifications, 20)  # 20 notifications per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'notification/notification_list.html', {
        'page_obj': page_obj,
    })

@login_required
def notification_detail(request, notification_id):
    """View to display a single notification"""
    user_type = get_user_type(request.user)
    notification = get_object_or_404(Notification, id=notification_id)
    
    if not notification.read_at:
        notification.read_at = timezone.now()
        notification.save()

    
    return render(request, 'notification/notification_detail.html', {
        'notification': notification,
        'user_type': user_type
    })

# Notification preferences functionality removed

@login_required
@require_POST
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    result = NotificationService.mark_as_read(notification.id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(result)
    else:
        return redirect('notification:notification_list')

# API views for notifications
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_notification_list(request):
    """API endpoint to get user's notifications"""
    user_type = get_user_type(request.user)
    
    # Base query - filter by recipient
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    
    # Filter by type if specified
    notification_type = request.query_params.get('type')
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    
    # Filter by status if specified
    status = request.query_params.get('status')
    if status:
        notifications = notifications.filter(status=status)
    
    # Limit results
    limit = int(request.query_params.get('limit', 20))
    notifications = notifications[:limit]
    
    # Format response
    result = [{
        'id': str(n.id),
        'type': n.notification_type,
        'subject': n.subject,
        'content': n.content,
        'status': n.status,
        'created_at': n.created_at.isoformat(),
        'sent_at': n.sent_at.isoformat() if n.sent_at else None,
        'read_at': n.read_at.isoformat() if n.read_at else None,
        'category': getattr(n, 'category', None),
    } for n in notifications]
    
    return Response({
        'count': len(result),
        'results': result,
        'user_type': user_type
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_mark_notification_read(request, notification_id):
    """API endpoint to mark a notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    result = NotificationService.mark_as_read(notification.id)
    return Response(result)

# API notification preferences endpoint removed

# API update preferences endpoint removed
