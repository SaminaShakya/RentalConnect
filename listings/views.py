from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required

from .models import Property, Booking, PropertyDeleteReason
from .forms import PropertyForm


def home(request):
    bookings = None
    owner_properties = []

    # TENANT DATA
    if request.user.is_authenticated and request.user.is_tenant:
        bookings = Booking.objects.filter(
            tenant=request.user
        ).order_by('-id')

    # OWNER DATA
    if request.user.is_authenticated and request.user.is_landlord:
        owner_properties = Property.objects.filter(
            landlord=request.user
        ).order_by('-created_at')

        # add booked status manually
        for prop in owner_properties:
            prop.is_booked = Booking.objects.filter(
                property=prop,
                approved=True
            ).exists()

    featured_properties = Property.objects.all()[:6]

    return render(request, 'listings/home.html', {
        'featured_properties': featured_properties,
        'bookings': bookings,
        'owner_properties': owner_properties,
    })



def property_list(request):
    properties = Property.objects.all()

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
    property = get_object_or_404(Property, id=property_id)

    return render(request, 'listings/property_detail.html', {
        'property': property
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
        property = form.save(commit=False)
        property.landlord = request.user
        property.save()
        return redirect('home')

    return render(request, 'listings/add_property.html', {'form': form})


@login_required
def edit_property(request, property_id):
    property = get_object_or_404(Property, id=property_id, landlord=request.user)

    form = PropertyForm(request.POST or None, request.FILES or None, instance=property)
    if form.is_valid():
        form.save()
        return redirect('home')

    return render(request, 'listings/edit_property.html', {'form': form})


@login_required
def delete_property(request, property_id):
    property = get_object_or_404(Property, id=property_id, landlord=request.user)

    if request.method == 'POST':
        reason = request.POST.get('reason')
        PropertyDeleteReason.objects.create(
            property=property,
            reason=reason
        )
        property.delete()
        return redirect('home')

    return render(request, 'listings/delete_property.html', {
        'property': property
    })
