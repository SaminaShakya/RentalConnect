"""
URL configuration for rentalConnect project.
"""

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

from listings import views as listing_views
from users import views as user_views

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Public pages
    path('', listing_views.home, name='home'),
    path('properties/', listing_views.property_list, name='property_list'),
    path('property/<int:property_id>/', listing_views.property_detail, name='property_detail'),
    path('location/', listing_views.location, name='location'),
    path('about/', listing_views.about, name='about'),
    path('contact/', listing_views.contact, name='contact'),

    # Auth
    path('register/', user_views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html'
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(
        template_name='registration/logout.html'
    ), name='logout'),

    # Dashboard (IMPORTANT FIX)
    path('dashboard/', user_views.dashboard, name='dashboard'),

    # Users app urls (profile, etc.)
    path('users/', include('users.urls')),
]

# Media files (images)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
