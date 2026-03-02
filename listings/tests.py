from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from users.models import CustomUser
from .models import Property, Booking, BookingMessage, EarlyExitRequest, Settlement, InspectionReport, InspectionImage


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


class EarlyExitTests(TestCase):
    def setUp(self):
        self.landlord = CustomUser.objects.create_user(
            username="landlord2",
            password="password123",
            is_landlord=True,
        )
        self.tenant = CustomUser.objects.create_user(
            username="tenant3",
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
        self.booking = Booking.objects.create(
            tenant=self.tenant,
            property=self.prop,
            start_date=timezone.now().date() + timedelta(days=1),
            end_date=timezone.now().date() + timedelta(days=121),
            status="approved",
            monthly_rent=1000,
            security_deposit=2000,
            lock_in_months=3,
        )

    def test_create_exit_request_and_penalty(self):
        # penalty should equal half the security deposit by default
        desired = timezone.now().date() + timedelta(days=60)
        exit_req = EarlyExitRequest.objects.create(
            booking=self.booking,
            desired_move_out=desired,
        )
        self.assertIsNotNone(exit_req.notice_given_days)
        self.assertEqual(exit_req.penalty_amount, self.booking.security_deposit / 2)

    def test_settlement_calculation(self):
        desired = timezone.now().date() + timedelta(days=60)
        exit_req = EarlyExitRequest.objects.create(
            booking=self.booking,
            desired_move_out=desired,
        )
        # simulate inspection damage amount
        exit_req.deductions = 500
        exit_req.save()
        sett = Settlement.objects.create(exit_request=exit_req, lease=self.booking)
        # penalty should be half deposit + damage
        self.assertEqual(sett.total_due, (self.booking.security_deposit / 2) + 500)
        # tenant keeps whatever remains of the deposit
        self.assertEqual(sett.total_credit, self.booking.security_deposit - sett.total_due)
        # net refund should equal remaining credit (never negative)
        self.assertEqual(sett.net_refund_to_tenant, max(sett.total_credit, 0))

    def test_inspection_image_upload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        desired = timezone.now().date() + timedelta(days=60)
        exit_req = EarlyExitRequest.objects.create(
            booking=self.booking,
            desired_move_out=desired,
        )
        insp = InspectionReport.objects.create(exit_request=exit_req)
        # simulate file upload
        img = SimpleUploadedFile("photo.jpg", b"filedata", content_type="image/jpeg")
        from .models import InspectionImage
        InspectionImage.objects.create(report=insp, image=img)
        self.assertEqual(insp.images.count(), 1)


class LocationSearchTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="locuser",
            password="pass",
            is_tenant=True,
        )
        self.landlord = CustomUser.objects.create_user(
            username="loclandlord",
            password="pass",
            is_landlord=True,
        )
        # three properties around two coordinates
        self.prop1 = Property.objects.create(
            landlord=self.landlord,
            title="A",
            description="",
            city="C",
            rent="100",
            bedrooms=1,
            bathrooms=1,
            address="1",
            latitude=0.0,
            longitude=0.0,
            is_verified=True,
        )
        self.prop2 = Property.objects.create(
            landlord=self.landlord,
            title="B",
            description="",
            city="C",
            rent="100",
            bedrooms=1,
            bathrooms=1,
            address="2",
            latitude=0.0,
            longitude=1.0,
            is_verified=True,
        )
        self.prop3 = Property.objects.create(
            landlord=self.landlord,
            title="C",
            description="",
            city="C",
            rent="100",
            bedrooms=1,
            bathrooms=1,
            address="3",
            latitude=1.0,
            longitude=0.0,
            is_verified=True,
        )

    def test_nearest_properties_util(self):
        from .utils import nearest_properties
        start = (0.0, 0.1)
        coords = {
            self.prop1.id: (self.prop1.latitude, self.prop1.longitude),
            self.prop2.id: (self.prop2.latitude, self.prop2.longitude),
            self.prop3.id: (self.prop3.latitude, self.prop3.longitude),
        }
        nearest = nearest_properties(start, coords, k=3)
        # prop1 should be closest then prop2 or prop3 depending on Haversine
        self.assertEqual(nearest[0], self.prop1.id)

    def test_property_list_nearby_order(self):
        client = self.client
        start_lat = 0.0
        start_lng = 0.1
        response = client.get(f"/listings/properties/?lat={start_lat}&lng={start_lng}")
        self.assertEqual(response.status_code, 200)
        props = response.context['page_obj'].object_list
        # first property should be prop1
        self.assertEqual(props[0].id, self.prop1.id)


from django.test import override_settings


@override_settings(ALLOWED_HOSTS=['testserver','localhost','127.0.0.1'])
class BookingActionTests(TestCase):
    """Verify tenant/landlord interactive actions (cancel, finalize, message)."""
    def setUp(self):
        # use unique usernames to avoid conflicts if test reruns create users
        self.landlord, _ = CustomUser.objects.get_or_create(
            username="landlord_act",
            defaults={'is_landlord': True}
        )
        self.landlord.set_password('password123')
        self.landlord.save()
        self.tenant, _ = CustomUser.objects.get_or_create(
            username="tenant_act",
            defaults={'is_tenant': True}
        )
        self.tenant.set_password('password123')
        self.tenant.save()
        self.prop = Property.objects.create(
            landlord=self.landlord,
            title="Action Property",
            description="Action prop",
            city="ActCity",
            rent="500.00",
            bedrooms=1,
            bathrooms=1,
            address="12 Act St",
            is_verified=True,
        )
        # create an approved booking in the future
        self.booking = Booking.objects.create(
            tenant=self.tenant,
            property=self.prop,
            start_date=timezone.now().date() + timedelta(days=5),
            end_date=timezone.now().date() + timedelta(days=15),
            status="approved",
        )

    def test_tenant_can_cancel_before_start(self):
        client = self.client
        logged = client.login(username="tenant_act", password="password123")
        self.assertTrue(logged, "tenant login failed")
        # Django test client automatically handles CSRF
        response = client.post(f"/listings/booking/{self.booking.id}/cancel/", {
            'cancellation_reason': 'Change of plans'
        })
        print('TEST DEBUG: cancel response', response.status_code)
        self.assertEqual(response.status_code, 302)
        self.booking.refresh_from_db()
        print('TEST DEBUG: booking after POST:', self.booking.status, self.booking.cancellation_reason)
        self.assertEqual(self.booking.status, 'cancelled')
        self.assertEqual(self.booking.cancellation_reason, 'Change of plans')

    def test_landlord_can_finalize_approved(self):
        client = self.client
        logged = client.login(username="landlord_act", password="password123")
        self.assertTrue(logged, "landlord login failed")
        response = client.post(f"/listings/booking/{self.booking.id}/finalize/", {})
        print('TEST DEBUG: finalize response', response.status_code)
        self.assertEqual(response.status_code, 302)
        self.booking.refresh_from_db()
        print('TEST DEBUG: booking after finalize POST:', self.booking.status, self.booking.finalized_at)
        self.assertEqual(self.booking.status, 'rented_out')
        self.assertIsNotNone(self.booking.finalized_at)

    def test_booking_messaging_flow(self):
        # tenant sends a message to landlord
        client = self.client
        logged = client.login(username="tenant_act", password="password123")
        self.assertTrue(logged, "tenant login failed for messaging")
        response = client.post(f"/listings/booking/{self.booking.id}/messages/", {'message': 'Hello!'} )
        print('TEST DEBUG: message post response', response.status_code)
        self.assertEqual(response.status_code, 302)
        # message should exist and unread for landlord
        msg = BookingMessage.objects.filter(booking=self.booking).first()
        print('TEST DEBUG: message after POST:', msg)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.content, 'Hello!')
        self.assertFalse(msg.is_read)
        # landlord views messages, which should mark it read
        client.logout()
        client.login(username="landlord_act", password="password123")
        resp2 = client.get(f"/listings/booking/{self.booking.id}/messages/")
        self.assertEqual(resp2.status_code, 200)
        msg.refresh_from_db()
        self.assertTrue(msg.is_read)
