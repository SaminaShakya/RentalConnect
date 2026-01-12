from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required

from .models import CustomUser, Profile
from .forms import ProfileForm
from listings.models import Property, Booking


# =========================
# USER REGISTRATION
# =========================
def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role')

        if not username or not password or not role:
            return render(request, 'registration/register.html', {
                'error': 'All fields are required'
            })

        if CustomUser.objects.filter(username=username).exists():
            return render(request, 'registration/register.html', {
                'error': 'Username already exists'
            })

        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # clear roles first
        user.is_tenant = False
        user.is_landlord = False

        if role == 'tenant':
            user.is_tenant = True
        elif role == 'landlord':
            user.is_landlord = True

        user.save()
        login(request, user)
        return redirect('dashboard')

    return render(request, 'registration/register.html')


# =========================
# DASHBOARD (ROLE BASED)
# =========================
@login_required
def dashboard(request):
    user = request.user

    context = {
        'is_admin': user.is_superuser,
        'is_tenant': user.is_tenant,
        'is_landlord': user.is_landlord,
        'bookings': [],
        'properties': [],
    }

    if user.is_tenant:
        context['bookings'] = Booking.objects.filter(
            tenant=user
        ).order_by('-created_at')

    elif user.is_landlord:
        context['properties'] = Property.objects.filter(
            landlord=user
        ).order_by('-created_at')

        context['bookings'] = Booking.objects.filter(
            property__landlord=user
        ).order_by('-created_at')

    return render(request, 'users/dashboard.html', context)

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
