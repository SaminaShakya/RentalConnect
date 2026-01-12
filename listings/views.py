from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required

from .models import Property, Booking, PropertyDeleteReason
from .forms import PropertyForm, BookingForm



def home(request):
    bookings = None
    owner_properties = []

    # TENANT DATA
    if request.user.is_authenticated and request.user.is_tenant:
        bookings = Booking.objects.filter(
            tenant=request.user
        ).order_by('-created_at')

    # OWNER DATA
    if request.user.is_authenticated and request.user.is_landlord:
        owner_properties = Property.objects.filter(
            landlord=request.user
        ).order_by('-created_at')

        for prop in owner_properties:
            prop.is_booked = Booking.objects.filter(
                property=prop,
                status='approved'
            ).exists()

    featured_properties = Property.objects.filter(
        is_verified=True
    ).order_by('-created_at')[:6]

    return render(request, 'listings/home.html', {
        'featured_properties': featured_properties,
        'bookings': bookings,
        'owner_properties': owner_properties,
    })


def property_list(request):
    properties = Property.objects.filter(is_verified=True)

    city = request.GET.get('city')
    max_rent = request.GET.get('max_rent')

    if city:
        properties = properties.filter(city__icontains=city)

    if max_rent:
        properties = properties.filter(rent__lte=max_rent)

    return render(request, 'listings/property_list.html', {
        'properties': properties
    })


def property_detail(request, property_id):
    prop = get_object_or_404(
        Property,
        id=property_id,
        is_verified=True
    )

    return render(request, 'listings/property_detail.html', {
        'property': prop
    })


def location(request):
    return render(request, 'location.html')


def about(request):
    return render(request, 'about.html')


def contact(request):
    if request.method == 'POST':
        return render(request, 'contact.html', {
            'success': True,
            'message': 'Thank you! Your message has been sent successfully.'
        })
    return render(request, 'contact.html')


@login_required
def add_property(request):
    if not request.user.is_landlord:
        return redirect('home')

    form = PropertyForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        prop = form.save(commit=False)
        prop.landlord = request.user
        prop.is_verified = False  # admin must verify
        prop.save()
        return redirect('home')

    return render(request, 'listings/add_property.html', {'form': form})


@login_required
def edit_property(request, property_id):
    prop = get_object_or_404(
        Property,
        id=property_id,
        landlord=request.user
    )

    # 🔴 ALGORITHM: BLOCK EDIT IF APPROVED BOOKING EXISTS
    has_approved_booking = Booking.objects.filter(
        property=prop,
        status='approved'
    ).exists()

    if has_approved_booking:
        return redirect('dashboard')

    form = PropertyForm(
        request.POST or None,
        request.FILES or None,
        instance=prop
    )

    if form.is_valid():
        form.save()
        return redirect('dashboard')

    return render(request, 'listings/edit_property.html', {
        'form': form
    })


@login_required
def delete_property(request, property_id):
    prop = get_object_or_404(
        Property,
        id=property_id,
        landlord=request.user
    )

    # 🔴 ALGORITHM: BLOCK DELETE IF APPROVED BOOKING EXISTS
    has_approved_booking = Booking.objects.filter(
        property=prop,
        status='approved'
    ).exists()

    if has_approved_booking:
        return render(request, 'listings/delete_property.html', {
            'property': prop,
            'error': 'This property cannot be deleted because it has approved bookings.'
        })

    if request.method == 'POST':
        reason = request.POST.get('reason')
        PropertyDeleteReason.objects.create(
            property=prop,
            reason=reason
        )
        prop.delete()
        return redirect('dashboard')

    return render(request, 'listings/delete_property.html', {
        'property': prop
    })


@login_required
def request_booking(request, property_id):
    prop = get_object_or_404(
        Property,
        id=property_id,
        is_verified=True
    )

    # Only tenants can book
    if not request.user.is_tenant:
        return redirect('home')

    if request.method == 'POST':
        form = BookingForm(request.POST)

        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']

            # 🔥 ALGORITHM 1: DATE OVERLAP CHECK
            conflict_exists = Booking.objects.filter(
                property=prop,
                status__in=['approved', 'pending'],
                start_date__lt=end_date,
                end_date__gt=start_date
            ).exists()

            if conflict_exists:
                form.add_error(
                    None,
                    "This property is already booked for the selected dates."
                )
            else:
                booking = form.save(commit=False)
                booking.property = prop
                booking.tenant = request.user
                booking.status = 'pending'
                booking.save()
                return redirect('dashboard')
    else:
        form = BookingForm()

    return render(request, 'listings/request_booking.html', {
        'form': form,
        'property': prop
    })


@login_required
def manage_booking(request, booking_id, action):
    booking = get_object_or_404(Booking, id=booking_id)

    # SECURITY CHECK: only landlord of this property can approve/reject
    if not request.user.is_landlord:
        return redirect('dashboard')

    if booking.property.landlord != request.user:
        return redirect('dashboard')

    # Only allow valid actions
    if action not in ['approve', 'reject']:
        return redirect('dashboard')

    if action == 'approve':
        booking.status = 'approved'
    elif action == 'reject':
        booking.status = 'rejected'

    booking.save()
    return redirect('dashboard')
