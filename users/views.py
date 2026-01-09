from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from .models import CustomUser, Profile
from .forms import ProfileForm
from listings.models import Property
from listings.models import Booking


# =========================
# USER REGISTRATION
# =========================
def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        phone = request.POST.get('phone')
        user_type = request.POST.get('user_type', 'tenant')

        if password1 != password2:
            return render(request, 'registration/register.html', {
                'error': 'Passwords do not match'
            })

        try:
            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                password=password1,
                phone=phone
            )

            # Role assignment
            if user_type == 'tenant':
                user.is_tenant = True
            else:
                user.is_landlord = True

            user.save()
            login(request, user)

            return redirect('dashboard')

        except Exception:
            return render(request, 'registration/register.html', {
                'error': 'Username already exists or invalid data'
            })

    return render(request, 'registration/register.html')


# =========================
# USER LOGIN (ROLE BASED)
# =========================
def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)

            if user.is_superuser:
                return redirect('/admin/')

            return redirect('dashboard')

        return render(request, 'registration/login.html', {
            'error': 'Invalid username or password'
        })

    return render(request, 'registration/login.html')


# =========================
# DASHBOARD (ALL ROLES)
# =========================
from listings.models import Property, Booking

@login_required
def dashboard(request):
    user = request.user

    properties = []
    bookings = []

    if user.is_tenant:
        properties = Property.objects.all().order_by('-created_at')[:6]
        bookings = Booking.objects.filter(tenant=user).order_by('-id')

    context = {
        'is_admin': user.is_superuser,
        'is_landlord': user.is_landlord,
        'is_tenant': user.is_tenant,
        'properties': properties,
        'bookings': bookings,
    }

    return render(request, 'users/dashboard.html', context)



# =========================
# PROFILE CREATE / UPDATE
# =========================
@login_required
def update_profile(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'users/update_profile.html', {'form': form})
