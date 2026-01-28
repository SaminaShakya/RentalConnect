from django import forms
from .models import Property, Booking, PropertyVerificationRequest


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

        if start and end:
            if start >= end:
                raise forms.ValidationError(
                    "End date must be after start date."
                )
            
            # Check for DATE OVERLAPS, not just existence
            if self.tenant and self.property:
                conflicts = Booking.objects.filter(
                    property=self.property,
                    status__in=['approved', 'pending'],
                    start_date__lt=end,
                    end_date__gt=start
                )
                
                # Exclude current booking if editing
                if self.instance.pk:
                    conflicts = conflicts.exclude(pk=self.instance.pk)
                    
                if conflicts.exists():
                    raise forms.ValidationError(
                        "This property is already booked for the selected dates."
                    )

        return cleaned_data


class PropertyVerificationRequestForm(forms.ModelForm):
    class Meta:
        model = PropertyVerificationRequest
        fields = ['ownership_proof', 'address_proof', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'ownership_proof': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'address_proof': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
