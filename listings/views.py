from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Exists, OuterRef, Q, Avg, Count, F
from django.db.models.functions import Abs

from .models import Property, Booking, PropertyDeleteReason, PropertyVerificationRequest
from .forms import PropertyForm, BookingForm, PropertyVerificationRequestForm
from users.models import Notification
from users.models import CustomUser


def home(request):
    bookings = None
    owner_properties = []
    landlord_bookings = None
    stats = {}

    # TENANT DATA
    if request.user.is_authenticated and request.user.is_tenant:
        bookings = Booking.objects.filter(
            tenant=request.user
        ).select_related('property').order_by('-created_at')
        stats = {
            'total_bookings': bookings.count(),
            'pending_bookings': bookings.filter(status='pending').count(),
            'approved_bookings': bookings.filter(status='approved').count(),
            'rejected_bookings': bookings.filter(status='rejected').count(),
        }

    # OWNER DATA
    if request.user.is_authenticated and request.user.is_landlord:
        owner_properties = Property.objects.filter(
            landlord=request.user
        ).annotate(
            is_booked=Exists(
                Booking.objects.filter(
                    property=OuterRef('pk'),
                    status='approved'
                )
            )
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

        stats = {
            'total_properties': owner_properties.count(),
            'verified_properties': owner_properties.filter(is_verified=True).count(),
            'unverified_properties': owner_properties.filter(is_verified=False).count(),
            'total_booking_requests': landlord_bookings.count(),
            'pending_booking_requests': landlord_bookings.filter(status='pending').count(),
        }

    # FEATURED PROPERTIES WITH POPULARITY ALGORITHM
    featured_properties = get_popular_properties(limit=6)

    # Pagination for featured properties
    paginator = Paginator(featured_properties, 6)  # 6 properties per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'listings/home.html', {
        'page_obj': page_obj,
        'bookings': bookings,
        'owner_properties': owner_properties,
        'landlord_bookings': landlord_bookings,
        'stats': stats,
        'is_admin': request.user.is_authenticated and request.user.is_superuser,
        'is_tenant': request.user.is_authenticated and request.user.is_tenant,
        'is_landlord': request.user.is_authenticated and request.user.is_landlord,
    })


def _notify_admins(title: str, message: str, target_url: str = "/admin/"):
    for admin_user in CustomUser.objects.filter(is_superuser=True, is_active=True):
        Notification.objects.create(
            recipient=admin_user,
            actor=None,
            title=title,
            message=message,
            target_url=target_url,
        )


@login_required
def request_property_verification(request, property_id):
    prop = get_object_or_404(
        Property,
        id=property_id,
        landlord=request.user,
    )

    # If already verified, no need to request
    if prop.is_verified:
        return redirect('home')

    # Block duplicate pending requests
    if PropertyVerificationRequest.objects.filter(property=prop, status='pending').exists():
        return redirect('home')

    if request.method == 'POST':
        form = PropertyVerificationRequestForm(request.POST, request.FILES)
        if form.is_valid():
            vr = form.save(commit=False)
            vr.property = prop
            vr.submitted_by = request.user
            vr.status = 'pending'
            vr.save()

            # Notify admins
            _notify_admins(
                title="Property verification requested",
                message=f"Verification requested for '{prop.title}' by {request.user.username}.",
                target_url="/admin/listings/propertyverificationrequest/",
            )

            # Notify landlord
            Notification.objects.create(
                recipient=request.user,
                actor=request.user,
                title="Verification request submitted",
                message=f"Your verification request for '{prop.title}' was submitted. Admin will review it.",
                target_url="/#dashboard",
            )

            return redirect('home')
    else:
        form = PropertyVerificationRequestForm()

    return render(request, 'listings/request_verification.html', {
        'property': prop,
        'form': form,
    })


# =========================
# POPULARITY ALGORITHM
# =========================
def get_popular_properties(limit=6):
    """
    Popularity algorithm that ranks properties based on:
    - Recent bookings (40% weight)
    - Recent creation (30% weight) 
    - Verified status (30% weight)
    """
    from django.utils import timezone
    from datetime import timedelta

    # Calculate scores for properties
    thirty_days_ago = timezone.now() - timedelta(days=30)

    # Annotate properties with popularity scores
    properties = Property.objects.filter(is_verified=True).annotate(
        # Recent bookings count (last 30 days)
        recent_bookings=Count(
            'booking',
            filter=Q(
                booking__created_at__gte=thirty_days_ago,
                booking__status__in=['approved', 'pending']
            )
        )
    )

    # Calculate final scores
    scored_properties = []
    for prop in properties:
        # Normalize scores
        booking_score = min(prop.recent_bookings * 10, 40)  # Max 40 points for bookings
        
        # Recency score (newer properties get higher scores)
        days_old = (timezone.now().date() - prop.created_at.date()).days
        recency_score = max(0, 30 - days_old) if days_old <= 30 else 0  # Max 30 points for recency
        
        verified_bonus = 30 if prop.is_verified else 0  # 30 points for verified

        total_score = booking_score + recency_score + verified_bonus
        scored_properties.append((prop, total_score))

    # Sort by score and return top properties
    scored_properties.sort(key=lambda x: x[1], reverse=True)
    return [prop for prop, score in scored_properties[:limit]]


def property_list(request):
    query = request.GET.get('q', '').strip()  # General search query
    city = request.GET.get('city', '').strip()
    max_rent = request.GET.get('max_rent', '').strip()
    sort = request.GET.get('sort', 'newest').strip()

    # Use fuzzy search if there's a general query
    if query:
        properties = fuzzy_search_properties(query)
        # Convert to queryset for further filtering
        property_ids = [p.id for p in properties]
        properties = Property.objects.filter(id__in=property_ids)
    else:
        properties = Property.objects.filter(is_verified=True)

    # Apply additional filters
    if city:
        properties = properties.filter(city__icontains=city)

    if max_rent:
        try:
            max_rent_val = float(max_rent)
            properties = properties.filter(rent__lte=max_rent_val)
        except ValueError:
            pass  # Ignore invalid max_rent values

    # Sorting
    if sort == 'rent_low':
        properties = properties.order_by('rent', '-created_at')
    elif sort == 'rent_high':
        properties = properties.order_by('-rent', '-created_at')
    else:
        properties = properties.order_by('-created_at')

    # Pagination
    paginator = Paginator(properties, 10)  # 10 properties per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'listings/property_list.html', {
        'page_obj': page_obj,
        'search_query': query,
        'city_filter': city,
        'max_rent_filter': max_rent,
        'sort': sort,
    })


def property_detail(request, property_id):
    prop = get_object_or_404(
        Property,
        id=property_id,
        is_verified=True
    )

    # Get recommended properties based on similarity
    recommendations = get_property_recommendations(prop, limit=4)

    return render(request, 'listings/property_detail.html', {
        'property': prop,
        'recommendations': recommendations,
    })


# =========================
# RECOMMENDATION ALGORITHM
# =========================
def get_property_recommendations(target_property, limit=4):
    """
    Content-based filtering recommendation algorithm.
    Recommends properties similar to the target property based on:
    - Same city (highest weight)
    - Similar price range (±20%)
    - Similar bedroom/bathroom count
    - Different property (not the same one)
    - Verified properties only
    """
    # Base queryset - exclude current property and unverified
    similar_properties = Property.objects.filter(
        is_verified=True
    ).exclude(id=target_property.id)

    # Calculate similarity scores
    recommendations = []

    for prop in similar_properties:
        score = 0

        # City match (highest weight: 40 points)
        if prop.city.lower() == target_property.city.lower():
            score += 40

        # Price similarity (30 points max)
        price_diff = abs(float(prop.rent) - float(target_property.rent))
        price_range = float(target_property.rent) * 0.2  # 20% range
        if price_diff <= price_range:
            # Closer prices get higher scores
            price_score = 30 * (1 - price_diff / (price_range + 1))
            score += max(0, price_score)

        # Bedroom match (15 points)
        if prop.bedrooms == target_property.bedrooms:
            score += 15

        # Bathroom match (15 points)
        if prop.bathrooms == target_property.bathrooms:
            score += 15

        # Only include properties with meaningful similarity
        if score >= 20:  # Minimum threshold
            recommendations.append((prop, score))

    # Sort by score (highest first) and return top recommendations
    recommendations.sort(key=lambda x: x[1], reverse=True)
    return [prop for prop, score in recommendations[:limit]]


# =========================
# FUZZY SEARCH ALGORITHM
# =========================
def fuzzy_search_properties(query, max_results=20):
    """
    Fuzzy search algorithm for property search.
    Uses multiple strategies:
    1. Exact matches first
    2. Contains matches
    3. Similar sounding words (basic phonetic matching)
    """
    if not query or len(query.strip()) < 2:
        return Property.objects.filter(is_verified=True)[:max_results]

    query = query.strip().lower()
    results = []

    # Strategy 1: Exact city matches
    exact_city = Property.objects.filter(
        city__iexact=query,
        is_verified=True
    )
    results.extend(exact_city)

    # Strategy 2: City contains query
    city_contains = Property.objects.filter(
        city__icontains=query,
        is_verified=True
    ).exclude(id__in=[p.id for p in results])
    results.extend(city_contains)

    # Strategy 3: Title contains query
    title_contains = Property.objects.filter(
        title__icontains=query,
        is_verified=True
    ).exclude(id__in=[p.id for p in results])
    results.extend(title_contains)

    # Strategy 4: Description contains query
    desc_contains = Property.objects.filter(
        description__icontains=query,
        is_verified=True
    ).exclude(id__in=[p.id for p in results])
    results.extend(desc_contains)

    # Strategy 5: Address contains query
    address_contains = Property.objects.filter(
        address__icontains=query,
        is_verified=True
    ).exclude(id__in=[p.id for p in results])
    results.extend(address_contains)

    # Strategy 6: Basic phonetic similarity for city names
    phonetic_matches = get_phonetic_matches(query, max_results - len(results))
    for prop in phonetic_matches:
        if prop not in results:
            results.append(prop)

    return results[:max_results]


def get_phonetic_matches(query, limit=5):
    """
    Basic phonetic matching for city names.
    Simplified Soundex-like algorithm.
    """
    def get_soundex_code(word):
        """Generate a simple Soundex-like code"""
        if not word:
            return ""

        # Convert to uppercase and keep first letter
        word = word.upper()
        code = word[0]

        # Mapping for similar sounds
        mapping = {
            'BFPV': '1', 'CGJKQSXZ': '2', 'DT': '3',
            'L': '4', 'MN': '5', 'R': '6'
        }

        # Convert remaining letters
        for char in word[1:]:
            for key, value in mapping.items():
                if char in key:
                    if not code.endswith(value):  # Avoid duplicates
                        code += value
                    break
            else:
                # Keep vowels and other chars as-is, but limit length
                if len(code) < 4:
                    code += char

        # Pad or truncate to 4 characters
        return (code + '000')[:4]

    query_code = get_soundex_code(query)

    # Find properties with similar sounding city names
    similar_cities = []
    for prop in Property.objects.filter(is_verified=True):
        city_code = get_soundex_code(prop.city)
        if city_code == query_code:
            similar_cities.append(prop)

    return similar_cities[:limit]


def location(request):
    return render(request, 'location.html')


def about(request):
    return render(request, 'about.html')


def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        message = request.POST.get('message', '').strip()
        
        if name and email and message:
            try:
                # Send email to admin
                send_mail(
                    subject=f'Rental Connect Contact: {name}',
                    message=f'From: {name} ({email})\n\nMessage:\n{message}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.DEFAULT_FROM_EMAIL],  # Send to admin
                    fail_silently=False,
                )
                
                # Send confirmation email to user
                send_mail(
                    subject='Thank you for contacting Rental Connect',
                    message=f'Dear {name},\n\nThank you for contacting us. We have received your message and will get back to you soon.\n\nYour message:\n{message}\n\nBest regards,\nRental Connect Team',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                
                return render(request, 'contact.html', {
                    'success': True,
                    'message': 'Thank you! Your message has been sent successfully.'
                })
            except Exception as e:
                return render(request, 'contact.html', {
                    'error': 'Sorry, there was an error sending your message. Please try again later.'
                })
        else:
            return render(request, 'contact.html', {
                'error': 'Please fill in all fields.'
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

        Notification.objects.create(
            recipient=request.user,
            actor=request.user,
            title="Property submitted for verification",
            message=f"Your property '{prop.title}' was submitted and is awaiting admin verification.",
            target_url="/#dashboard",
        )
        return redirect('home')

    return render(request, 'listings/add_property.html', {'form': form})


@login_required
def edit_property(request, property_id):
    prop = get_object_or_404(
        Property,
        id=property_id,
        landlord=request.user
    )

    # BLOCK EDIT IF APPROVED BOOKING EXISTS
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

    # BLOCK DELETE IF APPROVED BOOKING EXISTS
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
        # Pass tenant/property so the form can validate overlaps consistently
        form = BookingForm(request.POST, tenant=request.user, property=prop)

        if form.is_valid():
            booking = form.save(commit=False)
            booking.property = prop
            booking.tenant = request.user
            booking.status = 'pending'

            try:
                # Run validation from Booking model (date overlap, invalid dates)
                booking.save()

                # Notify landlord about new booking request
                Notification.objects.create(
                    recipient=prop.landlord,
                    actor=request.user,
                    title="New booking request",
                    message=f"{request.user.username} requested {prop.title} ({booking.start_date} → {booking.end_date}).",
                    target_url="/#dashboard",
                )
                return redirect('dashboard')
            except ValidationError as e:
                # Display errors from clean() method
                for field, messages in e.message_dict.items():
                    for msg in messages:
                        form.add_error(field, msg)

    else:
        form = BookingForm(tenant=request.user, property=prop)

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

    # Notify tenant about decision
    Notification.objects.create(
        recipient=booking.tenant,
        actor=request.user,
        title=f"Booking {booking.status}",
        message=f"Your booking request for {booking.property.title} was {booking.status}.",
        target_url="/#dashboard",
    )
    return redirect('dashboard')
