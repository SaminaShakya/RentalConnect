from django.urls import path
from django.views.generic import RedirectView
from . import views, admin_views, payments

urlpatterns = [
    path('bookings/<int:booking_id>/messages/', RedirectView.as_view(pattern_name='booking_messages', permanent=False)),
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

    # Payment Gateway Integration
    path('settlement/<int:settlement_id>/payment/', payments.payment_gateway_selection, name='payment_gateway_selection'),
    path('settlement/<int:settlement_id>/stripe/initiate/', payments.initiate_stripe_payment, name='initiate_stripe_payment'),
    path('settlement/<int:settlement_id>/esewa/initiate/', payments.initiate_esewa_payment, name='initiate_esewa_payment'),
    path('settlement/<int:settlement_id>/khalti/initiate/', payments.initiate_khalti_payment, name='initiate_khalti_payment'),
    path('payment/success/', payments.payment_success, name='payment_success'),
    path('payment/cancel/', payments.payment_cancel, name='payment_cancel'),
    path('payment/webhook/stripe/', payments.stripe_webhook, name='stripe_webhook'),
    path('payment/success/', payments.payment_success, name='payment_success'),
    path('payment/cancel/', payments.payment_cancel, name='payment_cancel'),

    # Admin Dashboard
    path('admin/dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('admin/properties/', admin_views.admin_properties, name='admin_properties'),
    path('admin/bookings/', admin_views.admin_bookings, name='admin_bookings'),
    path('admin/verifications/', admin_views.admin_verifications, name='admin_verifications'),
    path('admin/settlements/', admin_views.admin_settlements, name='admin_settlements'),
    path('admin/users/', admin_views.admin_users, name='admin_users'),
    path('admin/verification/<int:verification_id>/review/', admin_views.verify_property, name='verify_property'),
    path('admin/property/<int:property_id>/toggle-verification/', admin_views.toggle_property_verification, name='toggle_property_verification'),

    # Static pages
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('location/', views.location, name='location'),
]
