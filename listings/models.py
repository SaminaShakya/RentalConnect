from django.db import models
from users.models import CustomUser

class Property(models.Model):
    landlord = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    description = models.TextField()
    city = models.CharField(max_length=50)
    rent = models.DecimalField(max_digits=10, decimal_places=2)
    bedrooms = models.IntegerField()
    bathrooms = models.IntegerField()
    address = models.TextField()
    image = models.ImageField(upload_to='property_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Booking(models.Model):
    tenant = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    approved = models.BooleanField(default=False)

class PropertyDeleteReason(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    reason = models.TextField()
    deleted_at = models.DateTimeField(auto_now_add=True)

