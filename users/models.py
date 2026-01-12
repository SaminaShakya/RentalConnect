from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class CustomUser(AbstractUser):
    is_tenant = models.BooleanField(default=False)
    is_landlord = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # Ensure user cannot be both tenant and landlord
        if self.is_tenant and self.is_landlord:
            raise ValueError("User cannot be both tenant and landlord")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    full_name = models.CharField(max_length=100)
    photo = models.ImageField(
        upload_to='profile_photos/',
        blank=True,
        null=True
    )
    phone = models.CharField(max_length=15, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.full_name
