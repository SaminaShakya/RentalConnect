from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import (
    Property, Booking, PropertyVerificationRequest,
    EarlyExitRequest, Settlement, BookingMessage
)
from users.models import CustomUser, Notification


def is_admin(user):
    return user.is_staff or user.is_superuser


@user_passes_test(is_admin)
def admin_dashboard(request):
    """Custom admin dashboard with key metrics and actions."""
    # Key metrics
    total_properties = Property.objects.count()
    verified_properties = Property.objects.filter(is_verified=True).count()
    pending_verifications = PropertyVerificationRequest.objects.filter(status='pending').count()
    total_bookings = Booking.objects.count()
    active_bookings = Booking.objects.filter(
        status='approved',
        end_date__gte=timezone.now().date()
    ).count()
    pending_bookings = Booking.objects.filter(status='pending').count()
    total_users = CustomUser.objects.count()
    active_users = CustomUser.objects.filter(
        last_login__gte=timezone.now() - timedelta(days=30)
    ).count()

    # Recent activities
    recent_bookings = Booking.objects.select_related('property', 'tenant').order_by('-created_at')[:5]
    recent_verifications = PropertyVerificationRequest.objects.select_related(
        'property', 'submitted_by'
    ).filter(status='pending').order_by('-created_at')[:5]
    recent_exits = EarlyExitRequest.objects.select_related(
        'booking__property', 'booking__tenant'
    ).order_by('-created_at')[:5]

    # Settlement statistics
    completed_settlements = Settlement.objects.filter(status='completed').count()
    disputed_settlements = Settlement.objects.filter(status='disputed').count()
    pending_payments = Settlement.objects.filter(
        status='completed',
        payment_status__in=['pending', 'processing']
    ).count()

    context = {
        'total_properties': total_properties,
        'verified_properties': verified_properties,
        'pending_verifications': pending_verifications,
        'total_bookings': total_bookings,
        'active_bookings': active_bookings,
        'pending_bookings': pending_bookings,
        'total_users': total_users,
        'active_users': active_users,
        'recent_bookings': recent_bookings,
        'recent_verifications': recent_verifications,
        'recent_exits': recent_exits,
        'completed_settlements': completed_settlements,
        'disputed_settlements': disputed_settlements,
        'pending_payments': pending_payments,
    }

    return render(request, 'admin/dashboard.html', context)


@user_passes_test(is_admin)
def admin_properties(request):
    """Admin view for managing properties."""
    properties = Property.objects.select_related('landlord').prefetch_related('images').order_by('-created_at')

    # Filters
    status_filter = request.GET.get('status', 'all')
    city_filter = request.GET.get('city', '')

    if status_filter == 'verified':
        properties = properties.filter(is_verified=True)
    elif status_filter == 'unverified':
        properties = properties.filter(is_verified=False)

    if city_filter:
        properties = properties.filter(city__icontains=city_filter)

    context = {
        'properties': properties,
        'status_filter': status_filter,
        'city_filter': city_filter,
    }

    return render(request, 'admin/properties.html', context)


@user_passes_test(is_admin)
def admin_bookings(request):
    """Admin view for managing bookings."""
    bookings = Booking.objects.select_related('property__landlord', 'tenant').order_by('-created_at')

    # Filters
    status_filter = request.GET.get('status', 'all')
    date_filter = request.GET.get('date', '')

    if status_filter != 'all':
        bookings = bookings.filter(status=status_filter)

    if date_filter:
        if date_filter == 'today':
            bookings = bookings.filter(created_at__date=timezone.now().date())
        elif date_filter == 'week':
            week_ago = timezone.now() - timedelta(days=7)
            bookings = bookings.filter(created_at__gte=week_ago)
        elif date_filter == 'month':
            month_ago = timezone.now() - timedelta(days=30)
            bookings = bookings.filter(created_at__gte=month_ago)

    context = {
        'bookings': bookings,
        'status_filter': status_filter,
        'date_filter': date_filter,
    }

    return render(request, 'admin/bookings.html', context)


@user_passes_test(is_admin)
def admin_verifications(request):
    """Admin view for managing property verifications."""
    verifications = PropertyVerificationRequest.objects.select_related(
        'property__landlord', 'submitted_by'
    ).order_by('-created_at')

    status_filter = request.GET.get('status', 'pending')
    if status_filter != 'all':
        verifications = verifications.filter(status=status_filter)

    context = {
        'verifications': verifications,
        'status_filter': status_filter,
    }

    return render(request, 'admin/verifications.html', context)


@user_passes_test(is_admin)
def admin_settlements(request):
    """Admin view for managing settlements."""
    settlements = Settlement.objects.select_related(
        'exit_request__booking__property',
        'exit_request__booking__tenant'
    ).order_by('-created_on')

    status_filter = request.GET.get('status', 'all')
    payment_filter = request.GET.get('payment', 'all')

    if status_filter != 'all':
        settlements = settlements.filter(status=status_filter)

    if payment_filter != 'all':
        settlements = settlements.filter(payment_status=payment_filter)

    context = {
        'settlements': settlements,
        'status_filter': status_filter,
        'payment_filter': payment_filter,
    }

    return render(request, 'admin/settlements.html', context)


@user_passes_test(is_admin)
def admin_users(request):
    """Admin view for managing users."""
    users = CustomUser.objects.annotate(
        property_count=Count('properties'),
        booking_count=Count('bookings_as_tenant')
    ).order_by('-date_joined')

    role_filter = request.GET.get('role', 'all')
    status_filter = request.GET.get('status', 'all')

    if role_filter == 'landlord':
        users = users.filter(is_landlord=True)
    elif role_filter == 'tenant':
        users = users.filter(is_tenant=True)

    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)

    context = {
        'users': users,
        'role_filter': role_filter,
        'status_filter': status_filter,
    }

    return render(request, 'admin/users.html', context)


@user_passes_test(is_admin)
def verify_property(request, verification_id):
    """Approve or reject property verification."""
    if request.method != 'POST':
        return redirect('admin_verifications')

    verification = get_object_or_404(PropertyVerificationRequest, id=verification_id)
    action = request.POST.get('action')

    if action == 'approve':
        verification.status = 'approved'
        verification.property.is_verified = True
        verification.property.save()
        messages.success(request, f"Property '{verification.property.title}' has been verified.")
    elif action == 'reject':
        verification.status = 'rejected'
        messages.warning(request, f"Property verification for '{verification.property.title}' has been rejected.")

    verification.save()

    # Create notification for property owner
    Notification.objects.create(
        recipient=verification.submitted_by,
        title='Property Verification Update',
        message=f"Your property '{verification.property.title}' verification has been {verification.status}.",
        target_url=f"/listings/property/{verification.property.id}/"
    )

    return redirect('admin_verifications')


@user_passes_test(is_admin)
def toggle_property_verification(request, property_id):
    """Toggle property verification status."""
    if request.method != 'POST':
        return redirect('admin_properties')

    property_obj = get_object_or_404(Property, id=property_id)
    property_obj.is_verified = not property_obj.is_verified
    property_obj.save()

    status = "verified" if property_obj.is_verified else "unverified"
    messages.success(request, f"Property '{property_obj.title}' has been {status}.")

    return redirect('admin_properties')