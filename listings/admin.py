from django.contrib import admin
from .models import (
    Property,
    Booking,
    PropertyDeleteReason,
    PropertyVerificationRequest,
    BookingMessage,
    EarlyExitRequest,
    InspectionReport,
    Settlement,
    InspectionImage,
    PropertyImage,
)
from users.models import Notification


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = ('image', 'uploaded_at')
    readonly_fields = ('uploaded_at',)


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
    inlines = [PropertyImageInline]


@admin.register(PropertyVerificationRequest)
class PropertyVerificationRequestAdmin(admin.ModelAdmin):
    list_display = ('property', 'submitted_by', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('property__title', 'submitted_by__username')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['approve_requests', 'reject_requests']

    def approve_requests(self, request, queryset):
        for vr in queryset:
            vr.status = 'approved'
            vr.reviewed_by = request.user
            vr.save(update_fields=['status', 'reviewed_by', 'updated_at'])

            # Mark property as verified
            prop = vr.property
            if not prop.is_verified:
                prop.is_verified = True
                prop.save(update_fields=['is_verified'])

            Notification.objects.create(
                recipient=prop.landlord,
                actor=request.user,
                title="Property verified",
                message=f"Your property '{prop.title}' has been verified and is now visible to tenants.",
                target_url="/#dashboard",
            )

    approve_requests.short_description = "Approve selected verification requests"

    def reject_requests(self, request, queryset):
        for vr in queryset:
            vr.status = 'rejected'
            vr.reviewed_by = request.user
            vr.save(update_fields=['status', 'reviewed_by', 'updated_at'])

            prop = vr.property
            Notification.objects.create(
                recipient=prop.landlord,
                actor=request.user,
                title="Verification rejected",
                message=f"Verification for '{prop.title}' was rejected. Please review requirements and resubmit.",
                target_url="/#dashboard",
            )

    reject_requests.short_description = "Reject selected verification requests"


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'property',
        'tenant',
        'status',
        'start_date',
        'end_date',
        'monthly_rent',
        'security_deposit',
    )
    list_filter = ('status',)
    search_fields = ('property__title', 'tenant__username')


@admin.register(EarlyExitRequest)
class EarlyExitRequestAdmin(admin.ModelAdmin):
    list_display = ('booking', 'status', 'request_date', 'desired_move_out')
    list_filter = ('status',)
    search_fields = ('booking__property__title', 'booking__tenant__username')
    readonly_fields = ('request_date', 'owner_response_date', 'penalty_amount', 'refund_amount', 'deductions')


class InspectionImageInline(admin.TabularInline):
    model = InspectionImage
    extra = 0

@admin.register(InspectionReport)
class InspectionReportAdmin(admin.ModelAdmin):
    list_display = ('exit_request', 'status', 'scheduled_date', 'damage_assessed_amount')
    list_filter = ('status',)
    search_fields = ('exit_request__booking__property__title',)
    inlines = [InspectionImageInline]


@admin.register(InspectionImage)
class InspectionImageAdmin(admin.ModelAdmin):
    list_display = ('report', 'uploaded_at')
    readonly_fields = ('uploaded_at',)


@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display = ('exit_request', 'status', 'net_refund_to_tenant', 'net_payable_to_owner')
    list_filter = ('status',)
    search_fields = ('exit_request__booking__property__title',)


@admin.register(PropertyDeleteReason)
class PropertyDeleteReasonAdmin(admin.ModelAdmin):
    list_display = ('property', 'deleted_at')


@admin.register(BookingMessage)
class BookingMessageAdmin(admin.ModelAdmin):
    list_display = ('booking', 'sender', 'created_at', 'is_read')
    list_filter = ('is_read', 'created_at')
    search_fields = ('booking__property__title', 'sender__username', 'content')
    readonly_fields = ('created_at', 'booking', 'sender')
