import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rentalConnect.settings')
import django
django.setup()

from django.test import Client
from listings.models import Booking, Property
from users.models import CustomUser
from django.utils import timezone
from datetime import timedelta

# create data
landlord = CustomUser.objects.create_user(username='landlord_act', password='password123', is_landlord=True)
tenant = CustomUser.objects.create_user(username='tenant_act', password='password123', is_tenant=True)
prop = Property.objects.create(landlord=landlord, title='Test', description='', city='C', rent='100', bedrooms=1, bathrooms=1, address='A', is_verified=True)
booking = Booking.objects.create(tenant=tenant, property=prop, start_date=timezone.now().date()+timedelta(days=5), end_date=timezone.now().date()+timedelta(days=15), status='approved')

client = Client()
print('login tenant', client.login(username='tenant_act', password='password123'))
resp = client.post(f"/booking/{booking.id}/cancel/", {'cancellation_reason': 'Change'})
print('cancel resp', resp.status_code, resp.url if hasattr(resp,'url') else '')
booking.refresh_from_db()
print('booking after cancel', booking.status, booking.cancellation_reason)

client.logout()
print('login landlord', client.login(username='landlord_act', password='password123'))
resp2 = client.post(f"/booking/{booking.id}/finalize/")
print('finalize resp', resp2.status_code, resp2.url if hasattr(resp2,'url') else '')
booking.refresh_from_db()
print('booking after finalize', booking.status, booking.finalized_at)
