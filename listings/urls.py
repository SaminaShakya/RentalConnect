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
    path('property/<int:property_id>/verify/', views.request_property_verification, name='request_property_verification'),

    # Booking system
    path('property/<int:property_id>/book/', views.request_booking, name='request_booking'),
    
    # Booking messaging & actions (must come before generic manage_booking pattern)
    path('booking/<int:booking_id>/messages/', views.booking_messages, name='booking_messages'),
    path('booking/<int:booking_id>/detail/', views.booking_detail, name='booking_detail'),
    path('booking/<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('booking/<int:booking_id>/finalize/', views.finalize_booking, name='finalize_booking'),
    
    # Generic booking management action (approve/reject)
    path('booking/<int:booking_id>/<str:action>/', views.manage_booking, name='manage_booking'),

    # Property appointments/viewings
    path('property/<int:property_id>/appointment/', views.request_appointment, name='request_appointment'),
    path('property/<int:property_id>/appointments/', views.view_appointments, name='view_appointments'),
    path('appointment/<int:appointment_id>/<str:action>/', views.manage_appointment, name='manage_appointment'),

    # Early exit
    path('booking/<int:booking_id>/exit/request/', views.request_early_exit, name='request_early_exit'),
    path('exit/<int:exit_id>/', views.early_exit_detail, name='early_exit_detail'),
    path('exit/<int:exit_id>/review/<str:action>/', views.owner_review_exit, name='owner_review_exit'),
    path('exit/<int:exit_id>/schedule/', views.schedule_inspection, name='schedule_inspection'),
    path('exit/<int:exit_id>/inspection/submit/', views.submit_inspection_report, name='submit_inspection_report'),
    path('exit/<int:exit_id>/settlement/', views.view_settlement, name='view_settlement'),

    # Static pages
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('location/', views.location, name='location'),
]
