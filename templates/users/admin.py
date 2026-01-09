from django.contrib import admin
from .models import Property, Booking

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('title', 'city', 'rent', 'landlord', 'created_at')
    list_filter = ('city',)
    search_fields = ('title', 'city', 'address')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('property', 'tenant', 'start_date', 'end_date', 'approved')
    list_filter = ('approved',)
    search_fields = ('property__title', 'tenant__username')
