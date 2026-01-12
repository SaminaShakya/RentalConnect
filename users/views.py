from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required

from .forms import UserRegisterForm, ProfileForm
from .models import Profile
from listings.models import Property, Booking


# =========================
# USER REGISTRATION
# =========================
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserRegisterForm()

    return render(request, 'registration/register.html', {'form': form})


# =========================
# USER LOGIN
# =========================
def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if user.is_superuser:
                return redirect('/admin/')

            return redirect('dashboard')

        return render(request, 'registration/login.html', {
            'error': 'Invalid username or password'
        })

    return render(request, 'registration/login.html')


# =========================
# DASHBOARD (ROLE BASED)
# =========================
@login_required
def dashboard(request):
    user = request.user

    context = {
        'is_admin': user.is_superuser,
        'is_landlord': user.is_landlord,
        'is_tenant': user.is_tenant,
    }

    if user.is_tenant:
        context['properties'] = Property.objects.filter(
            is_verified=True
        ).order_by('-created_at')[:6]

        context['bookings'] = Booking.objects.filter(
            tenant=user
        ).order_by('-created_at')

    elif user.is_landlord:
        context['properties'] = Property.objects.filter(
            owner=user
        ).order_by('-created_at')

        context['bookings'] = Booking.objects.filter(
            property__owner=user
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
