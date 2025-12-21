from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

class CustomUser(AbstractUser):
    is_tenant = models.BooleanField(default=False)
    is_landlord = models.BooleanField(default=False)
    phone = models.CharField(max_length=15, blank=True, null=True)

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='owner_photos/', blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)  # optional phone
    bio = models.TextField(blank=True, null=True)                    # optional bio

    def __str__(self):
        return self.full_name
