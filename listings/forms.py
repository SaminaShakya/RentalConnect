from django import forms
from .models import Property

class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            'title', 'description', 'city',
            'rent', 'bedrooms', 'bathrooms',
            'address', 'image'
        ]
