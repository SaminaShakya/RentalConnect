from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from users.models import CustomUser
from .models import Property, Booking


class BookingConflictTests(TestCase):
    def setUp(self):
        self.landlord = CustomUser.objects.create_user(
            username="landlord",
            password="password123",
            is_landlord=True,
        )
        self.tenant1 = CustomUser.objects.create_user(
            username="tenant1",
            password="password123",
            is_tenant=True,
        )
        self.tenant2 = CustomUser.objects.create_user(
            username="tenant2",
            password="password123",
            is_tenant=True,
        )

        self.prop = Property.objects.create(
            landlord=self.landlord,
            title="Test Property",
            description="Nice place",
            city="Testville",
            rent="1000.00",
            bedrooms=2,
            bathrooms=1,
            address="123 Test St",
            is_verified=True,
        )

    def test_booking_overlap_pending_is_blocked(self):
        start = timezone.now().date() + timedelta(days=5)
        end = start + timedelta(days=3)

        Booking.objects.create(
            tenant=self.tenant1,
            property=self.prop,
            start_date=start,
            end_date=end,
            status="pending",
        )

        # Overlapping booking should raise ValidationError via model clean()
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            Booking.objects.create(
                tenant=self.tenant2,
                property=self.prop,
                start_date=start + timedelta(days=1),
                end_date=end + timedelta(days=1),
                status="pending",
            )

    def test_booking_non_overlapping_is_allowed(self):
        start = timezone.now().date() + timedelta(days=5)
        end = start + timedelta(days=3)

        Booking.objects.create(
            tenant=self.tenant1,
            property=self.prop,
            start_date=start,
            end_date=end,
            status="approved",
        )

        # Non-overlapping (end == start) is allowed by our overlap check
        Booking.objects.create(
            tenant=self.tenant2,
            property=self.prop,
            start_date=end,
            end_date=end + timedelta(days=2),
            status="pending",
        )
