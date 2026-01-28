from django.test import TestCase

from .models import CustomUser
from .forms import SimpleRegisterForm


class RegistrationTests(TestCase):
    def test_register_tenant_sets_role(self):
        form = SimpleRegisterForm(data={
            "username": "u1",
            "email": "u1@example.com",
            "password": "Str0ngPass!123",
            "password_confirm": "Str0ngPass!123",
            "role": "tenant",
        })
        self.assertTrue(form.is_valid(), form.errors)
        user = form.create_user()
        self.assertTrue(user.is_tenant)
        self.assertFalse(user.is_landlord)

    def test_register_landlord_sets_role(self):
        form = SimpleRegisterForm(data={
            "username": "u2",
            "email": "u2@example.com",
            "password": "Str0ngPass!123",
            "password_confirm": "Str0ngPass!123",
            "role": "landlord",
        })
        self.assertTrue(form.is_valid(), form.errors)
        user = form.create_user()
        self.assertTrue(user.is_landlord)
        self.assertFalse(user.is_tenant)

    def test_email_duplicate_blocked_case_insensitive(self):
        CustomUser.objects.create_user(
            username="existing",
            email="Test@Example.com",
            password="password12345",
            is_tenant=True,
        )
        form = SimpleRegisterForm(data={
            "username": "newuser",
            "email": "test@example.com",
            "password": "Str0ngPass!123",
            "password_confirm": "Str0ngPass!123",
            "role": "tenant",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
