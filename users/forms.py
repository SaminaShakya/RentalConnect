from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import CustomUser, Profile


class UserRegisterForm(UserCreationForm):
    ROLE_CHOICES = (
        ('tenant', 'Tenant'),
        ('landlord', 'Landlord'),
    )

    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        role = self.cleaned_data.get('role')

        if role == 'tenant':
            user.is_tenant = True
        elif role == 'landlord':
            user.is_landlord = True

        # Normalize email to avoid duplicates differing by case/whitespace
        user.email = (user.email or "").strip().lower()

        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['full_name', 'phone', 'photo', 'bio']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class SimpleRegisterForm(forms.Form):
    """
    Registration form that matches the existing template field names:
    username, email, password, password_confirm, role
    """
    ROLE_CHOICES = (
        ('tenant', 'Tenant'),
        ('landlord', 'Landlord'),
    )

    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=False)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    password_confirm = forms.CharField(widget=forms.PasswordInput, required=True)
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True)

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            raise ValidationError("Username is required.")
        if CustomUser.objects.filter(username=username).exists():
            raise ValidationError("Username already exists.")
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if email and CustomUser.objects.filter(email__iexact=email).exists():
            raise ValidationError("Email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get('password')
        pw2 = cleaned.get('password_confirm')

        if pw and pw2 and pw != pw2:
            self.add_error('password_confirm', "Passwords do not match.")

        # Use Django's configured password validators (stronger + consistent)
        if pw:
            try:
                password_validation.validate_password(pw)
            except ValidationError as e:
                # ValidationError has .messages (list), not .message
                for msg in e.messages:
                    self.add_error('password', msg)

        return cleaned

    def create_user(self):
        if not self.is_valid():
            raise ValidationError("Form is not valid.")

        role = self.cleaned_data['role']
        user = CustomUser.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data.get('email', ''),
            password=self.cleaned_data['password'],
        )

        # Clear roles first, then set one
        user.is_tenant = False
        user.is_landlord = False
        if role == 'tenant':
            user.is_tenant = True
        else:
            user.is_landlord = True

        user.save()
        return user
