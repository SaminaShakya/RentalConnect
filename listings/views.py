from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Exists, OuterRef, Q, Avg, Count, F
from django.db.models.functions import Abs
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from PIL import Image
from io import BytesIO

from .models import (
    Property,
    Booking,
    PropertyDeleteReason,
    PropertyVerificationRequest,
    BookingMessage,
    EarlyExitRequest,
    InspectionReport,
    Settlement,
)
from .forms import (
    PropertyForm,
    BookingForm,
    PropertyVerificationRequestForm,
    EarlyExitRequestForm,
    InspectionReportForm,
    SettlementActionForm,
)
from users.models import Notification


# ============ Image Validation Utilities ============

def validate_image_file(image_file):
    """
    Validate image file: size, dimensions, format.
    Returns: (is_valid, error_message, image_info)
    """
    try:
        # Max file size: 5MB
        MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes
        if image_file.size > MAX_FILE_SIZE:
            return False, f"File size {image_file.size / (1024*1024):.1f}MB exceeds 5MB limit.", None
        
        # Check file extension
        allowed_exts = ['.jpg', '.jpeg', '.png', '.gif']
        file_name = image_file.name.lower()
        if not any(file_name.endswith(ext) for ext in allowed_exts):
            return False, "Only JPG, PNG, and GIF formats are allowed.", None
        
        # Validate image dimensions
        img = Image.open(image_file)
        width, height = img.size
        
        # Min dimensions: 640x480
        if width < 640 or height < 480:
            return False, f"Image too small. Minimum 640x480px, got {width}x{height}px.", None
        
        # Max dimensions: 4000x3000
        if width > 4000 or height > 3000:
            return False, f"Image too large. Maximum 4000x3000px, got {width}x{height}px.", None
        
        return True, None, {'width': width, 'height': height, 'format': img.format}
    
    except Exception as e:
        return False, f"Invalid image file: {str(e)}", None


def save_and_optimize_image(image_file):
    """
    Save and optimize image to ensure quality.
    Converts to RGB if needed, maintains aspect ratio.
    Returns: optimized image file
    """
    try:
        img = Image.open(image_file)
        
        # Convert RGBA to RGB (preserves quality)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # Save to BytesIO with quality settings
        output = BytesIO()
        img.save(output, format='JPEG', quality=90, optimize=True)
        output.seek(0)
        
        # Create a new InMemoryUploadedFile with the optimized image
        from django.core.files.uploadedfile import InMemoryUploadedFile
        optimized_file = InMemoryUploadedFile(
            output, 'ImageField',
            f"{image_file.name.split('.')[0]}.jpg",
            'image/jpeg',
            output.getbuffer().nbytes,
            None
        )
        return optimized_file
    
    except Exception as e:
        # If optimization fails, return original
        return image_file
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
        exit_requests = EarlyExitRequest.objects.filter(booking__tenant=request.user)
        stats = {
            'total_bookings': bookings.count(),
            'pending_bookings': bookings.filter(status='pending').count(),
            'approved_bookings': bookings.filter(status='approved').count(),
            'rejected_bookings': bookings.filter(status='rejected').count(),
            'exit_requests': exit_requests.count(),
            'pending_exits': exit_requests.filter(status='requested').count(),
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

        landlord_exits = EarlyExitRequest.objects.filter(booking__property__landlord=request.user)

        stats = {
            'total_properties': owner_properties.count(),
            'verified_properties': owner_properties.filter(is_verified=True).count(),
            'unverified_properties': owner_properties.filter(is_verified=False).count(),
            'total_booking_requests': landlord_bookings.count(),
            'pending_booking_requests': landlord_bookings.filter(status='pending').count(),
            'exit_requests': landlord_exits.count(),
            'pending_exit_requests': landlord_exits.filter(status='requested').count(),
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
        # convenience value for templates that need todays date
        'today': timezone.now().date(),
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


# ===== Early exit flow =====

@login_required
def request_early_exit(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id, tenant=request.user, status='approved')
    # prevent duplicate
    if hasattr(booking, 'early_exit'):
        return redirect('early_exit_detail', booking.early_exit.id)

    if request.method == 'POST':
        form = EarlyExitRequestForm(request.POST, booking=booking)
        if form.is_valid():
            ex = form.save(commit=False)
            ex.booking = booking
            ex.status = 'requested'
            ex.save()
            Notification.objects.create(
                recipient=booking.property.landlord,
                actor=request.user,
                title='Early exit requested',
                message=f"Tenant {request.user.username} has requested early exit for booking #{booking.id}.",
                target_url=f"/listings/exit/{ex.id}/",
            )
            return redirect('early_exit_detail', ex.id)
    else:
        form = EarlyExitRequestForm(booking=booking)
    return render(request, 'listings/early_exit_request.html', {'form': form, 'booking': booking})


@login_required
def early_exit_detail(request, exit_id):
    ex = get_object_or_404(EarlyExitRequest, pk=exit_id)
    # ensure only tenant or owner or admin
    if request.user not in [ex.booking.tenant, ex.booking.property.landlord] and not request.user.is_superuser:
        return redirect('home')
    # display status and actions depending on role
    return render(request, 'listings/early_exit_detail.html', {'exit': ex})


@login_required
def owner_review_exit(request, exit_id, action):
    ex = get_object_or_404(EarlyExitRequest, pk=exit_id)
    if request.user != ex.booking.property.landlord:
        return redirect('home')
    if ex.status != 'requested':
        return redirect('early_exit_detail', exit_id)

    if action == 'approve':
        ex.status = 'owner_approved'
        ex.owner_response_date = timezone.now()
        ex.save()
        Notification.objects.create(
            recipient=ex.booking.tenant,
            actor=request.user,
            title='Early exit approved',
            message=f"Your early exit request for booking #{ex.booking.id} was approved.",
            target_url=f"/listings/exit/{ex.id}/",
        )
    elif action == 'reject':
        ex.status = 'owner_rejected'
        ex.owner_response_date = timezone.now()
        ex.owner_comments = request.POST.get('comments','')
        ex.save()
        Notification.objects.create(
            recipient=ex.booking.tenant,
            actor=request.user,
            title='Early exit rejected',
            message=f"Your early exit request for booking #{ex.booking.id} was rejected.",
            target_url=f"/listings/exit/{ex.id}/",
        )
    return redirect('early_exit_detail', exit_id)


@login_required
def schedule_inspection(request, exit_id):
    ex = get_object_or_404(EarlyExitRequest, pk=exit_id)
    if request.user != ex.booking.property.landlord and not request.user.is_superuser:
        return redirect('home')
    # only schedule when owner_approved
    if ex.status != 'owner_approved':
        return redirect('early_exit_detail', exit_id)

    if request.method == 'POST':
        form = InspectionReportForm(request.POST)
        if form.is_valid():
            insp = form.save(commit=False)
            insp.exit_request = ex
            insp.status = 'pending'
            insp.save()
            ex.status = 'inspection_scheduled'
            ex.save()
            Notification.objects.create(
                recipient=ex.booking.tenant,
                actor=request.user,
                title='Inspection scheduled',
                message=f"Inspection for your early exit request #{ex.id} has been scheduled.",
                target_url=f"/listings/exit/{ex.id}/",
            )
            return redirect('early_exit_detail', exit_id)
    else:
        form = InspectionReportForm()
    return render(request, 'listings/inspection_schedule.html', {'form': form, 'exit': ex})


@login_required
def submit_inspection_report(request, exit_id):
    ex = get_object_or_404(EarlyExitRequest, pk=exit_id)
    if request.user != ex.booking.tenant and request.user != ex.booking.property.landlord:
        return redirect('home')
    insp = getattr(ex, 'inspection', None)
    if not insp or insp.status != 'pending':
        return redirect('early_exit_detail', exit_id)

    # In a real system checklist fields and images would be handled via JS
    if request.method == 'POST':
        insp.checklist = request.POST.get('checklist', {})
        insp.notes = request.POST.get('notes', '')
        insp.damage_assessed_amount = Decimal(request.POST.get('damage_amount','0') or '0')
        insp.status = 'completed'
        insp.save()
        # handle uploaded image (single)
        img = request.FILES.get('images')
        if img:
            from .models import InspectionImage
            InspectionImage.objects.create(report=insp, image=img)

        ex.status = 'inspection_completed'
        ex.save()
        # create settlement draft
        Settlement.objects.create(exit_request=ex, lease=ex.booking)
        Notification.objects.create(
            recipient=ex.booking.tenant,
            actor=request.user,
            title='Inspection completed',
            message=f"Inspection for exit request #{ex.id} completed. Settlement draft is ready.",
            target_url=f"/listings/exit/{ex.id}/",
        )
        return redirect('early_exit_detail', exit_id)
    return render(request, 'listings/inspection_report.html', {'inspection': insp, 'exit': ex})


@login_required
def view_settlement(request, exit_id):
    ex = get_object_or_404(EarlyExitRequest, pk=exit_id)
    settlement = getattr(ex, 'settlement', None)
    if not settlement:
        return redirect('early_exit_detail', exit_id)

    if request.method == 'POST':
        form = SettlementActionForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            comments = form.cleaned_data['comments']
            if action == 'accept':
                if request.user == ex.booking.tenant:
                    settlement.status = 'tenant_accepted'
                elif request.user == ex.booking.property.landlord:
                    settlement.status = 'owner_accepted'
                settlement.save()
            else:
                settlement.status = 'disputed'
                settlement.notes += f"\n{request.user.username}: {comments}"
                settlement.save()
            return redirect('early_exit_detail', exit_id)
    else:
        form = SettlementActionForm()
    return render(request, 'listings/settlement.html', {'settlement': settlement, 'exit': ex, 'form': form})


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
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')

    # Use fuzzy search if there's a general query
    if query:
        properties = fuzzy_search_properties(query)
        # Convert to queryset for further filtering
        property_ids = [p.id for p in properties]
        properties = Property.objects.filter(id__in=property_ids)
    else:
        properties = Property.objects.filter(is_verified=True)

    # if location provided perform distance ranking
    distance_ordered = False
    if lat and lng:
        try:
            lat_f = float(lat)
            lng_f = float(lng)
            # gather coords from filtered queryset
            coords = {
                p.id: (p.latitude, p.longitude)
                for p in properties
                if p.latitude is not None and p.longitude is not None
            }
            # compute ordering
            from .utils import nearest_properties
            ordered_ids = nearest_properties((lat_f, lng_f), coords, k=properties.count())
            # preserve initial filtering by using Case/When for ordering
            from django.db.models import Case, When
            preserved = Case(*[When(pk=pid, then=pos) for pos, pid in enumerate(ordered_ids)])
            properties = properties.filter(id__in=ordered_ids).order_by(preserved)
            distance_ordered = True
        except ValueError:
            pass

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
    if not distance_ordered:
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

    # Get active booking for the current user (if tenant)
    active_booking = None
    messages = []
    if request.user.is_authenticated and request.user.is_tenant:
        active_booking = Booking.objects.filter(
            tenant=request.user,
            property=prop,
            status__in=['approved', 'pending']
        ).first()
        
        if active_booking:
            messages = BookingMessage.objects.filter(
                booking=active_booking
            ).select_related('sender').order_by('created_at')

    # Compute convenience flags for template (avoid complex template expressions)
    can_cancel_active_booking = False
    can_finalize_active_booking = False
    if active_booking:
        today = timezone.now().date()
        if request.user.is_authenticated and request.user == active_booking.tenant:
            if active_booking.status in ['pending', 'approved'] and active_booking.start_date > today:
                can_cancel_active_booking = True
        if request.user.is_authenticated and request.user == active_booking.property.landlord:
            if active_booking.status == 'approved':
                can_finalize_active_booking = True

    return render(request, 'listings/property_detail.html', {
        'property': prop,
        'recommendations': recommendations,
        'active_booking': active_booking,
        'messages': messages,
        # date for template comparisons
        'today': timezone.now().date(),
        'can_cancel_active_booking': can_cancel_active_booking,
        'can_finalize_active_booking': can_finalize_active_booking,
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
    
    # Get uploaded images
    images_list = request.FILES.getlist('images') if request.method == 'POST' else []
    image_errors = []
    
    # Validate image count
    if len(images_list) == 0 and request.method == 'POST':
        image_errors.append("At least 1 image is required.")
    elif len(images_list) > 4:
        image_errors.append(f"Maximum 4 images allowed. You selected {len(images_list)}.")
    
    # Validate individual images
    valid_images = []
    for idx, image_file in enumerate(images_list, 1):
        is_valid, error_msg, img_info = validate_image_file(image_file)
        if not is_valid:
            image_errors.append(f"Image {idx}: {error_msg}")
        else:
            valid_images.append(image_file)
    
    if form.is_valid() and not image_errors and valid_images:
        try:
            prop = form.save(commit=False)
            prop.landlord = request.user
            prop.is_verified = False  # admin must verify
            prop.save()

            # Handle multiple image uploads with optimization
            from .models import PropertyImage
            for image_file in valid_images:
                # Optimize image before saving
                optimized = save_and_optimize_image(image_file)
                PropertyImage.objects.create(property=prop, image=optimized)

            Notification.objects.create(
                recipient=request.user,
                actor=request.user,
                title="Property submitted for verification",
                message=f"Your property '{prop.title}' was submitted and is awaiting admin verification.",
                target_url="/#dashboard",
            )
            return redirect('home')
        except Exception as e:
            if 'prop' in locals():
                prop.delete()
            image_errors.append(f"Error saving property: {str(e)}")

    return render(request, 'listings/add_property.html', {
        'form': form,
        'image_errors': image_errors
    })


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

    image_errors = []
    
    if form.is_valid():
        form.save()
        
        # Handle multiple image uploads (max 4 total)
        images_list = request.FILES.getlist('images')
        valid_images = []
        
        if images_list:
            from .models import PropertyImage
            current_count = prop.images.count()
            
            # Validate image count
            if current_count + len(images_list) > 4:
                image_errors.append(f"Property already has {current_count} images. Maximum 4 total allowed (you tried to add {len(images_list)}).")
            
            # Validate individual images
            for idx, image_file in enumerate(images_list, 1):
                is_valid, error_msg, img_info = validate_image_file(image_file)
                if not is_valid:
                    image_errors.append(f"Image {idx}: {error_msg}")
                else:
                    valid_images.append(image_file)
            
            # Save valid images
            if valid_images and not image_errors:
                try:
                    for image_file in valid_images:
                        # Optimize image before saving
                        optimized = save_and_optimize_image(image_file)
                        PropertyImage.objects.create(property=prop, image=optimized)
                except Exception as e:
                    image_errors.append(f"Error uploading images: {str(e)}")
        
        # If no errors, redirect to dashboard
        if not image_errors:
            return redirect('dashboard')

    # Get existing images for display in template
    existing_images = prop.images.all()

    return render(request, 'listings/edit_property.html', {
        'form': form,
        'existing_images': existing_images,
        'image_errors': image_errors
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

    form_errors = {}
    booking_error = None

    if request.method == 'POST':
        # Pass tenant/property so the form can validate overlaps consistently
        form = BookingForm(request.POST, tenant=request.user, property=prop)

        if form.is_valid():
            # Manually create booking with all required fields to avoid incomplete instance
            try:
                booking = Booking(
                    property=prop,
                    tenant=request.user,
                    start_date=form.cleaned_data['start_date'],
                    end_date=form.cleaned_data['end_date'],
                    status='pending',
                    monthly_rent=prop.rent,
                    # default deposit equal to one month rent (can be modified later)
                    security_deposit=prop.rent,
                    lock_in_months=0,
                )
                # Run validation from Booking model (date overlap, invalid dates)
                booking.full_clean()
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
                # Store booking-level validation errors separately
                if hasattr(e, 'message_dict'):
                    # Filter out __all__ key and just get the error messages
                    error_messages = []
                    for key, messages in e.message_dict.items():
                        for msg in messages:
                            error_messages.append(str(msg))
                    booking_error = ' '.join(error_messages) if error_messages else str(e)
                elif hasattr(e, 'message'):
                    booking_error = str(e.message)
                else:
                    booking_error = str(e)
        else:
            # Form validation failed - collect form errors
            form_errors = form.errors

    else:
        form = BookingForm(tenant=request.user, property=prop)

    return render(request, 'listings/request_booking.html', {
        'form': form,
        'form_errors': form_errors,
        'booking_error': booking_error,
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


# =========================
# BOOKING MESSAGING SYSTEM
# =========================
@login_required
def booking_messages(request, booking_id):
    """
    View/send messages for a specific booking.
    Both tenant and landlord can access and message here.
    Supports both dashboard and property modal message submissions.
    """
    from .models import BookingMessage
    
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Security check: only tenant or landlord of the property can message
    if request.user != booking.tenant and request.user != booking.property.landlord:
        return render(request, 'listings/forbidden.html', {
            'message': 'You are not authorized to access messages for this booking.',
            'booking': booking,
        })
    
    # Get all messages for this booking
    messages = booking.messages.all()
    
    # Mark messages as read for current user
    messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    
    # Get other user (tenant or landlord)
    if request.user == booking.tenant:
        other_user = booking.property.landlord
        user_role = "Tenant"
    else:
        other_user = booking.tenant
        user_role = "Landlord"
    
    # Handle message submission
    if request.method == 'POST':
        # Support both 'message' (from dashboard form) and 'content' (from property modal form)
        message_content = request.POST.get('message', '') or request.POST.get('content', '')
        message_content = message_content.strip()
        
        if message_content:
            BookingMessage.objects.create(
                booking=booking,
                sender=request.user,
                content=message_content
            )
            
            # Notify the other user about new message
            if request.user == booking.tenant:
                notif_recipient = booking.property.landlord
                notif_title = f"New message from tenant on {booking.property.title}"
            else:
                notif_recipient = booking.tenant
                notif_title = f"New message from landlord about {booking.property.title}"
            
            Notification.objects.create(
                recipient=notif_recipient,
                actor=request.user,
                title=notif_title,
                message=message_content[:100],
                target_url=f'/bookings/{booking_id}/messages/',
            )
            
            # Check if request came from property modal (next parameter)
            next_url = request.POST.get('next')
            if next_url:
                return redirect(next_url)
            
            return redirect('booking_messages', booking_id=booking_id)
    
    return render(request, 'listings/booking_messages.html', {
        'booking': booking,
        'messages': messages,
        'other_user': other_user,
        'user_role': user_role,
    })



@login_required
def booking_detail(request, booking_id):
    """
    View details of a booking with option to message.
    """
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Security check: only tenant or landlord can view
    if request.user != booking.tenant and request.user != booking.property.landlord:
        return render(request, 'listings/forbidden.html', {
            'message': 'You are not authorized to view this booking.',
            'booking': booking,
        })
    
    # Get unread message count
    unread_count = booking.messages.filter(is_read=False).exclude(sender=request.user).count()

    # compute actions availability
    today = timezone.now().date()
    can_cancel = (
        request.user == booking.tenant and
        booking.status in ['pending', 'approved'] and
        booking.start_date > today
    )
    can_finalize = (
        request.user == booking.property.landlord and
        booking.status == 'approved'
    )
    
    return render(request, 'listings/booking_detail.html', {
        'booking': booking,
        'unread_count': unread_count,
        'today': today,
        'can_cancel': can_cancel,
        'can_finalize': can_finalize,
    })


# =========================
# BOOKING CANCELLATION
# =========================
@login_required
def cancel_booking(request, booking_id):
    """
    Allow tenant to cancel their booking before check-in date.
    """
    booking = get_object_or_404(Booking, id=booking_id)
    # Security check: only tenant can cancel their own booking
    if request.user != booking.tenant:
        return redirect('dashboard')
    
    # Cannot cancel if already checked in or status is not pending/approved
    from datetime import date
    if booking.start_date <= date.today():
        return render(request, 'listings/cancel_booking.html', {
            'booking': booking,
            'error': 'Cannot cancel booking after check-in date has passed.'
        })
    
    if booking.status not in ['pending', 'approved']:
        return render(request, 'listings/cancel_booking.html', {
            'booking': booking,
            'error': f'Cannot cancel booking with status "{booking.get_status_display}".'
        })
    
    if request.method == 'POST':
        cancellation_reason = request.POST.get('cancellation_reason', '').strip()
        
        if not cancellation_reason:
            return render(request, 'listings/cancel_booking.html', {
                'booking': booking,
                'error': 'Please provide a cancellation reason.'
            })
        
        # Update booking status
        booking.status = 'cancelled'
        booking.cancellation_reason = cancellation_reason
        booking.save()
        
        # Notify landlord about cancellation
        Notification.objects.create(
            recipient=booking.property.landlord,
            actor=request.user,
            title=f"Booking Cancelled for {booking.property.title}",
            message=f"Tenant {request.user.username} cancelled their booking ({booking.start_date} → {booking.end_date}). Reason: {cancellation_reason[:100]}",
            target_url=f"/booking/{booking_id}/detail/",
        )
        
        # Clear any pending appointments for this booking
        from .models import PropertyAppointment
        PropertyAppointment.objects.filter(booking=booking, status__in=['pending', 'confirmed']).update(status='cancelled')
        
        return redirect('dashboard')
    
    return render(request, 'listings/cancel_booking.html', {
        'booking': booking,
    })


# =========================
# BOOKING FINALIZATION
# =========================
@login_required
def finalize_booking(request, booking_id):
    """
    Allow landlord to finalize (mark as rented_out) an approved booking.
    """
    from django.utils import timezone
    
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Security check: only landlord can finalize their property's booking
    if not request.user.is_landlord or booking.property.landlord != request.user:
        return redirect('dashboard')
    
    # Can only finalize approved bookings
    if booking.status != 'approved':
        return render(request, 'listings/finalize_booking.html', {
            'booking': booking,
            'error': f'Can only finalize approved bookings. Current status: {booking.get_status_display}'
        })
    
    if request.method == 'POST':
        # Mark as rented_out and set finalization timestamp
        booking.status = 'rented_out'
        booking.finalized_at = timezone.now()
        booking.save()
        
        # Notify tenant
        Notification.objects.create(
            recipient=booking.tenant,
            actor=request.user,
            title=f"Booking Finalized - {booking.property.title}",
            message=f"Your booking for {booking.property.title} has been finalized. Check-in: {booking.start_date}",
            target_url=f"/booking/{booking_id}/detail/",
        )
        
        return redirect('dashboard')
    
    return render(request, 'listings/finalize_booking.html', {
        'booking': booking,
    })


# =========================
# PROPERTY APPOINTMENTS/VIEWINGS
# =========================
@login_required
def request_appointment(request, property_id):
    """
    Tenant requests appointment to view a property.
    """
    from .models import PropertyAppointment
    from datetime import timedelta
    
    prop = get_object_or_404(Property, id=property_id, is_verified=True)
    
    # Only tenants can request appointments
    if not request.user.is_tenant:
        return redirect('home')
    
    min_date = (date.today() + timedelta(days=1)).isoformat()  # Can't book today
    error_message = None
    
    if request.method == 'POST':
        appointment_date = request.POST.get('appointment_date')
        appointment_time = request.POST.get('appointment_time')
        message = request.POST.get('message', '').strip()
        
        try:
            # Validate date is in future
            appt_date_obj = date.fromisoformat(appointment_date)
            if appt_date_obj <= date.today():
                raise ValueError("Appointment date must be in the future.")
            
            # Create appointment
            appointment = PropertyAppointment(
                property=prop,
                tenant=request.user,
                appointment_date=appt_date_obj,
                appointment_time=appointment_time,
                message=message,
            )
            appointment.full_clean()
            appointment.save()
            
            # Notify landlord
            Notification.objects.create(
                recipient=prop.landlord,
                actor=request.user,
                title=f"Appointment Request for {prop.title}",
                message=f"{request.user.username} requested an appointment on {appt_date_obj} at {appointment_time}.",
                target_url=f"/property/{property_id}/appointments/",
            )
            
            return render(request, 'listings/request_appointment.html', {
                'property': prop,
                'min_date': min_date,
                'success': True,
                'appointment': appointment,
            })
        
        except Exception as e:
            error_message = str(e)
    
    return render(request, 'listings/request_appointment.html', {
        'property': prop,
        'min_date': min_date,
        'error': error_message,
    })


@login_required
def manage_appointment(request, appointment_id, action):
    """
    Allow landlord to confirm/reject appointment requests.
    """
    from .models import PropertyAppointment
    
    appointment = get_object_or_404(PropertyAppointment, id=appointment_id)
    
    # Security check: only landlord can manage appointments
    if not request.user.is_landlord or appointment.property.landlord != request.user:
        return redirect('dashboard')
    
    # Only allow valid actions
    if action not in ['confirm', 'reject', 'cancel']:
        return redirect('dashboard')
    
    if action == 'confirm':
        appointment.status = 'confirmed'
        notif_title = "Appointment Confirmed ✓"
        notif_msg = f"Your appointment for {appointment.property.title} on {appointment.appointment_date} at {appointment.appointment_time} has been confirmed."
    elif action == 'reject':
        landlord_notes = request.POST.get('landlord_notes', '').strip() if request.method == 'POST' else ''
        appointment.status = 'rejected'
        appointment.landlord_notes = landlord_notes
        notif_title = "Appointment Rejected"
        notif_msg = f"Your appointment request for {appointment.property.title} has been rejected."
        if landlord_notes:
            notif_msg += f" Note: {landlord_notes[:100]}"
    else:  # cancel
        appointment.status = 'cancelled'
        notif_title = "Appointment Cancelled"
        notif_msg = f"Your appointment for {appointment.property.title} on {appointment.appointment_date} has been cancelled."
    
    appointment.save()
    
    # Notify tenant
    Notification.objects.create(
        recipient=appointment.tenant,
        actor=request.user,
        title=notif_title,
        message=notif_msg,
        target_url=f"/property/{appointment.property_id}/",
    )
    
    return redirect('dashboard')


@login_required
def view_appointments(request, property_id):
    """
    View all appointment requests for a property (landlord only).
    """
    from .models import PropertyAppointment
    
    prop = get_object_or_404(Property, id=property_id)
    
    # Security check: only landlord can view appointments
    if not request.user.is_landlord or prop.landlord != request.user:
        return redirect('dashboard')
    
    appointments = prop.appointments.all()
    pending_count = appointments.filter(status='pending').count()
    confirmed_count = appointments.filter(status='confirmed').count()
    
    return render(request, 'listings/property_appointments.html', {
        'property': prop,
        'appointments': appointments,
        'pending_count': pending_count,
        'confirmed_count': confirmed_count,
    })
