#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rentalConnect.settings')
django.setup()

from users.models import Notification

# Check all notifications related to booking
notifs = Notification.objects.filter(title__icontains='booking').values('id', 'title', 'target_url', 'created_at')
print(f"Total booking-related notifications: {notifs.count()}")
for n in notifs:
    print(f"  ID: {n['id']}, Title: {n['title']}, URL: {n['target_url']}")
