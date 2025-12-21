from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Property, Booking  

def home(request):
    
    featured_properties = Property.objects.all()[:6]
    
    return render(request, 'listings/home.html', {
        'featured_properties': featured_properties 
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

@login_required  
def dashboard(request):
    
    user_bookings = Booking.objects.filter(tenant=request.user)
    
    user_properties = Property.objects.filter(landlord=request.user)
    
    return render(request, 'users/dashboard.html', {
        'bookings': user_bookings,      
        'properties': user_properties   
    })

def location(request):
    return render(request, 'location.html')

def about(request):
    return render(request, 'about.html')

def contact(request):
    if request.method == 'POST':
        # Handle form submission here (you can add email sending logic later)
        return render(request, 'contact.html', {
            'success': True,
            'message': 'Thank you! Your message has been sent successfully.'
        })
    return render(request, 'contact.html')