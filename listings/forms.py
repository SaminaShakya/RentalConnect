from django import forms
from .models import Property, Booking, PropertyVerificationRequest, PropertyImage
from datetime import date


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
            'latitude',
            'longitude'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'rent': forms.NumberInput(attrs={'class': 'form-control'}),
            'bedrooms': forms.NumberInput(attrs={'class': 'form-control'}),
            'bathrooms': forms.NumberInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
        }


class BookingForm(forms.Form):
    """
    Simple form for booking dates without using ModelForm to avoid
    incomplete Booking instance issues.
    """
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Start Date'
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='End Date'
    )

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


# ============ Early Exit Forms ============

class EarlyExitRequestForm(forms.ModelForm):
    class Meta:
        model = None  # will set in __init__
        fields = ['desired_move_out']
        widgets = {
            'desired_move_out': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.booking = kwargs.pop('booking', None)
        super().__init__(*args, **kwargs)
        self.Meta.model = __import__('listings.models', fromlist=['EarlyExitRequest']).EarlyExitRequest

    def clean_desired_move_out(self):
        date_val = self.cleaned_data.get('desired_move_out')
        if not self.booking:
            return date_val
        # must be between today and booking end_date
        if date_val < date.today():
            raise forms.ValidationError("Move-out date cannot be in the past.")
        if date_val > self.booking.end_date:
            raise forms.ValidationError("Move-out date cannot be after lease end date.")
        # notice period enforcement (30 days default)
        notice = (date_val - date.today()).days
        if notice < getattr(self.booking, 'lock_in_months', 0) * 30:
            raise forms.ValidationError("Move-out date violates lock-in/notice period.")
        return date_val


class InspectionReportForm(forms.ModelForm):
    images = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        help_text='Upload a photo of the property condition.'
    )

    class Meta:
        model = __import__('listings.models', fromlist=['InspectionReport']).InspectionReport
        fields = ['scheduled_date', 'notes', 'images']
        widgets = {
            'scheduled_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class SettlementActionForm(forms.Form):
    action = forms.ChoiceField(choices=(('accept','Accept'),('dispute','Dispute')))
    comments = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))
