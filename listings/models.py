from django.db import models
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from users.models import CustomUser

class Property(models.Model):
    landlord = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='properties'
    )
    title = models.CharField(max_length=100)
    description = models.TextField()
    city = models.CharField(max_length=50, db_index=True)  # Added index
    rent = models.DecimalField(max_digits=10, decimal_places=2, db_index=True)  # Added index
    bedrooms = models.PositiveIntegerField()
    bathrooms = models.PositiveIntegerField()
    address = models.TextField()
    latitude = models.FloatField(null=True, blank=True, help_text="Decimal degrees")
    longitude = models.FloatField(null=True, blank=True, help_text="Decimal degrees")
    image = models.ImageField(
        upload_to='property_images/',
        blank=True,
        null=True,
        help_text="Primary property image (upload at least one image)"
    )
    is_verified = models.BooleanField(default=False, db_index=True)  # Added index
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']


class PropertyImage(models.Model):
    """Multiple images per property (max 4)"""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='property_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f"Image for {self.property.title}"

    def clean(self):
        """Ensure property doesn't exceed 4 images"""
        if self.property.images.exclude(id=self.id).count() >= 4:
            raise ValidationError("Maximum 4 images per property allowed.")


class Booking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('rented_out', 'Rented Out'),  # Finalized - property is occupied
        ('cancelled', 'Cancelled'),      # Tenant cancelled before checkout
        ('completed', 'Completed'),      # Tenancy ended normally
    )

    tenant = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    start_date = models.DateField(db_index=True)  # Added index
    end_date = models.DateField(db_index=True)    # Added index
    # snapshot of rent and security deposit when booking created
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    lock_in_months = models.PositiveIntegerField(default=0, help_text="Number of months tenant agrees not to exit early.")

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True  # Added index
    )
    cancellation_reason = models.TextField(blank=True, null=True, help_text="Reason for cancellation (if cancelled)")
    finalized_at = models.DateTimeField(blank=True, null=True, help_text="When landlord finalized the booking (rented_out)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.property.title} - {self.tenant.username}"

    # --------------------------
    # Booking Conflict Detection
    # --------------------------
    def clean(self):
        """
        This method runs before saving a Booking.
        Validates dates and checks for conflicts with existing approved bookings.
        """
        today = date.today()
        
        # Validate start date is not in the past (allow today and future)
        if self.start_date < today:
            raise ValidationError("Start date must be today or in the future.")
        
        # Validate end date is after start date
        if self.start_date >= self.end_date:
            raise ValidationError("End date must be after start date.")
        
        # Validate minimum booking duration (1 day)
        if (self.end_date - self.start_date).days < 1:
            raise ValidationError("Minimum booking duration is 1 day.")
        
        # Check for date overlaps with existing bookings.
        # We block overlaps for both approved and pending so multiple tenants
        # cannot reserve the same dates concurrently.
        conflicts = Booking.objects.filter(
            property=self.property,
            status__in=['approved', 'pending'],
            start_date__lt=self.end_date,
            end_date__gt=self.start_date
        )
        
        # Exclude self in case of updating existing booking
        if self.pk:
            conflicts = conflicts.exclude(pk=self.pk)

        if conflicts.exists():
            raise ValidationError("Booking dates conflict with an existing approved booking.")

    def save(self, *args, **kwargs):
        # Run clean() before saving to ensure conflict detection
        self.clean()
        super().save(*args, **kwargs)


class PropertyDeleteReason(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='delete_reasons'
    )
    reason = models.TextField()
    deleted_at = models.DateTimeField(auto_now_add=True)


class PropertyAppointment(models.Model):
    """
    Viewing/appointment scheduling system for properties.
    Allows tenants to request appointment times to view the property.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='appointments')
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='appointments', null=True, blank=True)
    tenant = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='appointment_requests')
    
    appointment_date = models.DateField(help_text="Date of appointment")
    appointment_time = models.TimeField(help_text="Preferred time of appointment")
    message = models.TextField(blank=True, help_text="Additional message/questions for landlord")
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    landlord_notes = models.TextField(blank=True, help_text="Landlord's response/notes")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-appointment_date', '-appointment_time']
        indexes = [
            models.Index(fields=['property', 'status']),
            models.Index(fields=['tenant', 'appointment_date']),
        ]
    
    def __str__(self):
        return f"Appointment: {self.property.title} on {self.appointment_date} at {self.appointment_time}"


# ----------------------------------
# Early tenant exit related models
# ----------------------------------

class EarlyExitRequest(models.Model):
    STATUS_CHOICES = (
        ('requested', 'Requested'),
        ('owner_approved', 'Owner Approved'),
        ('owner_rejected', 'Owner Rejected'),
        ('inspection_scheduled', 'Inspection Scheduled'),
        ('inspection_completed', 'Inspection Completed'),
        ('settlement_confirmed', 'Settlement Confirmed'),
        ('lease_terminated', 'Lease Terminated'),
        ('disputed', 'Disputed'),
    )

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='early_exit')
    request_date = models.DateTimeField(auto_now_add=True)
    desired_move_out = models.DateField()
    notice_given_days = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='requested', db_index=True)
    owner_response_date = models.DateTimeField(null=True, blank=True)
    owner_comments = models.TextField(blank=True)
    penalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"EarlyExit(Booking #{self.booking.id}) {self.status}"

    def calculate_notice(self):
        if self.booking and self.desired_move_out:
            self.notice_given_days = (self.desired_move_out - date.today()).days

    def calculate_penalty(self):
        # basic penalty formula: one month's rent per remaining month or as configured
        if self.booking.monthly_rent:
            remaining_days = (self.booking.end_date - self.desired_move_out).days
            remaining_months = remaining_days / 30
            rate = 1.0
            if self.booking.lock_in_months and remaining_months < self.booking.lock_in_months:
                rate = 1.5  # higher penalty during lock-in
            self.penalty_amount = self.booking.monthly_rent * remaining_months * rate
            if self.penalty_amount < 0:
                self.penalty_amount = 0

    def save(self, *args, **kwargs):
        self.calculate_notice()
        self.calculate_penalty()
        super().save(*args, **kwargs)


class InspectionReport(models.Model):
    exit_request = models.OneToOneField(EarlyExitRequest, on_delete=models.CASCADE, related_name='inspection')
    scheduled_date = models.DateTimeField(null=True, blank=True)
    inspector = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='inspections')
    status = models.CharField(max_length=20, choices=(('pending','Pending'),('completed','Completed')), default='pending')
    checklist = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    damage_assessed_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Inspection for exit #{self.exit_request.id} [{self.status}]"


class InspectionImage(models.Model):
    report = models.ForeignKey(InspectionReport, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='inspection_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Photo for {self.report}"

class Settlement(models.Model):
    exit_request = models.OneToOneField(EarlyExitRequest, on_delete=models.CASCADE, related_name='settlement')
    lease = models.ForeignKey(Booking, on_delete=models.CASCADE)
    total_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_payable_to_owner = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_refund_to_tenant = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    calculated_on = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=(('draft','Draft'),('tenant_accepted','Tenant Accepted'),('owner_accepted','Owner Accepted'),('disputed','Disputed'),('completed','Completed')), default='draft', db_index=True)
    notes = models.TextField(blank=True)

    def calculate(self):
        # compute dues and credits using data from exit_request and booking
        self.total_due = self.exit_request.penalty_amount
        # include unpaid rent if any (not tracked here, assume 0)
        self.total_credit = (self.exit_request.booking.security_deposit or 0) - self.exit_request.deductions
        self.net_refund_to_tenant = max(self.total_credit - self.total_due, 0)
        self.net_payable_to_owner = max(self.total_due - self.total_credit, 0)

    def save(self, *args, **kwargs):
        self.calculate()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Deleted: {self.property.title}"


class PropertyVerificationRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='verification_requests',
    )
    submitted_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='property_verification_requests',
    )
    ownership_proof = models.FileField(
        upload_to='verification_docs/',
        blank=True,
        null=True,
        help_text="Upload a document that proves ownership/authorization.",
    )
    address_proof = models.FileField(
        upload_to='verification_docs/',
        blank=True,
        null=True,
        help_text="Upload a utility bill/rent agreement/address proof.",
    )
    notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
    )
    admin_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_property_verifications',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Verification({self.property_id}) {self.status}"


class BookingMessage(models.Model):
    """
    Messages between tenant and landlord about a booking.
    Enables direct communication regarding booking requests and details.
    """
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='messages',
        db_index=True
    )
    sender = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='sent_booking_messages',
        db_index=True
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['booking', 'created_at']),
            models.Index(fields=['sender', 'is_read']),
        ]

    def __str__(self):
        return f"Message from {self.sender.username} on booking {self.booking.id}"
