from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required

from .models import Profile, Notification
from .forms import ProfileForm, SimpleRegisterForm
from django.db.models import Exists, OuterRef
from django.utils import timezone
from listings.models import Booking, Property, PropertyVerificationRequest, EarlyExitRequest
from listings.utils import haversine


# =========================
# USER REGISTRATION
# =========================
def register(request):
    """
    Uses SimpleRegisterForm so validation is centralized and consistent.
    Keeps compatibility with the existing template input names.
    """
    if request.method == 'POST':
        form = SimpleRegisterForm(request.POST)
        if form.is_valid():
            user = form.create_user()
            login(request, user)
            return redirect('dashboard')

        # Show first error as the top-level message (template expects `error`)
        first_error = None
        if form.errors:
            # Flatten all field + non-field errors
            for errs in form.errors.values():
                if errs:
                    first_error = errs[0]
                    break

        # Create a copy of errors without __all__ key (Django templates forbid underscore-prefixed attributes)
        form_errors_dict = dict(form.errors)
        nonfield_errors = form_errors_dict.pop('__all__', [])

        return render(request, 'registration/register.html', {
            'error': first_error,
            'form_errors': form_errors_dict,
            'nonfield_errors': nonfield_errors,
        })

    return render(request, 'registration/register.html', {
        'form_errors': {},
        'nonfield_errors': [],
    })


# =========================
# DASHBOARD (ROLE BASED)
# =========================
@login_required
def dashboard(request):
    bookings = None
    properties = None
    landlord_bookings = None
    stats = {}

    if request.user.is_tenant:
        bookings = Booking.objects.filter(
            tenant=request.user
        ).select_related('property', 'property__landlord').order_by('-created_at')

        # Add distance calculation if user location is available
        user_lat = request.session.get('user_lat')
        user_lng = request.session.get('user_lng')
        
        if user_lat and user_lng:
            for booking in bookings:
                if booking.property.latitude and booking.property.longitude:
                    booking.distance = haversine(
                        (float(user_lat), float(user_lng)),
                        (booking.property.latitude, booking.property.longitude)
                    )

        exit_requests = EarlyExitRequest.objects.filter(booking__tenant=request.user)
        stats = {
            'total_bookings': bookings.count(),
            'pending_bookings': bookings.filter(status='pending').count(),
            'approved_bookings': bookings.filter(status='approved').count(),
            'rejected_bookings': bookings.filter(status='rejected').count(),
            'active_bookings': bookings.filter(status__in=['approved', 'rented_out']).count(),
            'exit_requests': exit_requests.count(),
        }

    if request.user.is_landlord:
        properties = Property.objects.filter(
            landlord=request.user
        ).annotate(
            has_pending_verification=Exists(
                PropertyVerificationRequest.objects.filter(
                    property=OuterRef('pk'),
                    status='pending',
                )
            )
        ).order_by('-created_at')

        landlord_bookings = Booking.objects.filter(
            property__landlord=request.user
        ).select_related('property', 'tenant').order_by('-created_at')

        landlord_exits = EarlyExitRequest.objects.filter(booking__property__landlord=request.user)
        stats = {
            'total_properties': properties.count(),
            'verified_properties': properties.filter(is_verified=True).count(),
            'unverified_properties': properties.filter(is_verified=False).count(),
            'pending_booking_requests': landlord_bookings.filter(status='pending').count(),
            'active_tenants': landlord_bookings.filter(status='rented_out').count(),
            'exit_requests': landlord_exits.count(),
        }

    return render(request, 'users/dashboard.html', {
        'is_admin': request.user.is_superuser,
        'is_tenant': request.user.is_tenant,
        'is_landlord': request.user.is_landlord,
        'bookings': bookings if bookings is not None else [],
        'properties': properties if properties is not None else [],
        'landlord_bookings': landlord_bookings if landlord_bookings is not None else [],
        'early_exits': EarlyExitRequest.objects.filter(booking__tenant=request.user).select_related('booking', 'booking__property').order_by('-request_date') if request.user.is_tenant else [],
        'stats': stats,
        'today': timezone.now().date(),
    })


@login_required
def wishlist(request):
    # Placeholder UI until SavedProperty model is added.
    return render(request, 'users/wishlist.html')

# =========================
# PROFILE UPDATE
# =========================
@login_required
def update_profile(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = ProfileForm(
            request.POST,
            request.FILES,
            instance=profile
        )
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'users/update_profile.html', {'form': form})


# =========================
# NOTIFICATIONS (IN-APP)
# =========================
@login_required
def notifications_list(request):
    notifications = Notification.objects.filter(
        recipient=request.user
    ).select_related('actor')
    return render(request, 'users/notifications.html', {
        'notifications': notifications,
    })


@login_required
def notification_mark_read(request, notification_id):
    notif = Notification.objects.filter(
        id=notification_id,
        recipient=request.user
    ).first()
    if notif:
        notif.is_read = True
        notif.save(update_fields=['is_read'])

        # If it has a target URL, go there after marking read
        if notif.target_url:
            return redirect(notif.target_url)

    return redirect('notifications')


@login_required
def notifications_mark_all_read(request):
    if request.method == 'POST':
        Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(is_read=True)
    return redirect('notifications')
