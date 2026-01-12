from django import forms
from .models import Property, Booking


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            'title',
            'description',
            'city',
            'rent',
            'bedrooms',
            'bathrooms',
            'address',
            'image'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'rent': forms.NumberInput(attrs={'class': 'form-control'}),
            'bedrooms': forms.NumberInput(attrs={'class': 'form-control'}),
            'bathrooms': forms.NumberInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control'}),
        }


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'end_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}
            ),
        }

    def __init__(self, *args, **kwargs):
        # We pass tenant and property from the view
        self.tenant = kwargs.pop('tenant', None)
        self.property = kwargs.pop('property', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')

        if start and end and start >= end:
            raise forms.ValidationError(
                "End date must be after start date."
            )
        # Check for booking conflicts
        if self.tenant and self.property:
            conflict_exists = Booking.objects.filter(
                tenant=self.tenant,
                property=self.property,
                status__in=['pending', 'approved']
            ).exists()

            if conflict_exists:
                raise forms.ValidationError(
                    "This property is already booked for the selected dates."
                )

        return cleaned_data

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')

        if start and end and start >= end:
            raise forms.ValidationError(
                "End date must be after start date."
            )

        return cleaned_data
