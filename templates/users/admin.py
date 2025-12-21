from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

# Register your CustomUser model
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_tenant', 'is_landlord', 'is_staff', 'is_superuser')
    list_filter = ('is_tenant', 'is_landlord', 'is_staff', 'is_superuser')