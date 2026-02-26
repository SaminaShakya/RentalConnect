from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required

from .models import CustomUser, Profile
from .forms import ProfileForm, SimpleRegisterForm
from .models import Notification
from listings.models import Property, Booking


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
    # Unified experience: dashboard is embedded on Home.
    # Keep this URL for compatibility, but redirect to Home dashboard section.
    return redirect('home')

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
