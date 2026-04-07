#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rentalConnect.settings')
django.setup()

from users.models import Notification

# Delete all old notifications with /booking/ URLs
count = Notification.objects.filter(target_url__startswith='/booking/').count()
print(f"Found {count} old notifications with /booking/ URLs")

if count > 0:
    Notification.objects.filter(target_url__startswith='/booking/').delete()
    print(f"Deleted {count} old notifications")
else:
    print("No old notifications to delete")
