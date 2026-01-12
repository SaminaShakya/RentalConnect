from django.contrib import admin
from .models import Property, Booking, PropertyDeleteReason


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'city',
        'rent',
        'landlord',
        'is_verified',
        'created_at',
    )
    list_filter = ('is_verified', 'city')
    search_fields = ('title', 'city', 'landlord__username')
    list_editable = ('is_verified',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'property',
        'tenant',
        'status',
        'start_date',
        'end_date',
    )
    list_filter = ('status',)
    search_fields = ('property__title', 'tenant__username')


@admin.register(PropertyDeleteReason)
class PropertyDeleteReasonAdmin(admin.ModelAdmin):
    list_display = ('property', 'deleted_at')
