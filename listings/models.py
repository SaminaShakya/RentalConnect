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
    image = models.ImageField(
        upload_to='property_images/',
        blank=True,
        null=True
    )
    is_verified = models.BooleanField(default=False, db_index=True)  # Added index
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']


class Booking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    tenant = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    start_date = models.DateField(db_index=True)  # Added index
    end_date = models.DateField(db_index=True)    # Added index
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True  # Added index
    )
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
        
        # Validate start date is not in the past
        if self.start_date < today:
            raise ValidationError("Cannot book dates in the past.")
        
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
