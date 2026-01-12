from django.urls import path
from . import views

urlpatterns = [
    # Home
    path('', views.home, name='home'),

    # Property browsing
    path('properties/', views.property_list, name='property_list'),
    path('property/<int:property_id>/', views.property_detail, name='property_detail'),

    # Property management (landlord)
    path('add-property/', views.add_property, name='add_property'),
    path('edit-property/<int:property_id>/', views.edit_property, name='edit_property'),
    path('delete-property/<int:property_id>/', views.delete_property, name='delete_property'),

    # Booking system
    path('property/<int:property_id>/book/', views.request_booking, name='request_booking'),
    path('booking/<int:booking_id>/<str:action>/', views.manage_booking, name='manage_booking'),

    # Static pages
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('location/', views.location, name='location'),
]
