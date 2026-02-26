import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','rentalConnect.settings')
import django; django.setup()

from listings.views import cancel_booking, finalize_booking, booking_messages
from django.test import RequestFactory
from listings.models import Booking, Property
from users.models import CustomUser
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

factory = RequestFactory()

landlord, _ = CustomUser.objects.get_or_create(username='landlord_act', defaults={'is_landlord': True})
landlord.set_password('password123')
landlord.save()
tenant, _ = CustomUser.objects.get_or_create(username='tenant_act', defaults={'is_tenant': True})
tenant.set_password('password123')
tenant.save()
prop = Property.objects.create(landlord=landlord, title='Test', description='', city='C', rent='100', bedrooms=1, bathrooms=1, address='A', is_verified=True)
booking = Booking.objects.create(tenant=tenant, property=prop, start_date=timezone.now().date()+timedelta(days=5), end_date=timezone.now().date()+timedelta(days=15), status='approved')

# simulate post cancel
req = factory.post(f'/booking/{booking.id}/cancel/', {'cancellation_reason': 'Change'})
req.user = tenant
res = cancel_booking(req, booking.id)
print('direct cancel returned', res, 'booking status', Booking.objects.get(pk=booking.pk).status)

# simulate post finalize
req2 = factory.post(f'/booking/{booking.id}/finalize/')
req2.user = landlord
res2 = finalize_booking(req2, booking.id)
print('direct finalize returned', res2, 'booking status', Booking.objects.get(pk=booking.pk).status)
