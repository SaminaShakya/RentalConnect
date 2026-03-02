from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class CustomUser(AbstractUser):
    is_tenant = models.BooleanField(default=False, db_index=True)    # Added index
    is_landlord = models.BooleanField(default=False, db_index=True)  # Added index

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


class Notification(models.Model):
    """
    Simple in-app notifications.
    Stored in DB and shown in the UI.
    """
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_index=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications_sent",
    )
    title = models.CharField(max_length=120)
    message = models.TextField(blank=True)
    target_url = models.CharField(max_length=300, blank=True)  # relative URL (e.g. /property/1/)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"To {self.recipient}: {self.title}"
