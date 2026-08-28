from django import forms
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

from .models import Restaurant, Branch, RestaurantTable

phone_validator = RegexValidator(r"^\+?[0-9\-\s]{7,20}$", _('Enter a valid phone number.'))


class RestaurantProfileForm(forms.ModelForm):
    phone = forms.CharField(required=False, validators=[phone_validator], widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Restaurant
        fields = [
            'restaurant_name', 'logo', 'email', 'phone', 'description', 'address', 'city', 'state', 'country', 'pincode',
            'opening_time', 'closing_time', 'primary_color', 'secondary_color',
        ]
        widgets = {
            'restaurant_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.Select(attrs={'class': 'form-select'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control'}),
            'opening_time': forms.TimeInput(format='%H:%M', attrs={'class': 'form-control', 'type': 'time'}),
            'closing_time': forms.TimeInput(format='%H:%M', attrs={'class': 'form-control', 'type': 'time'}),
            'primary_color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
            'secondary_color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
        }


class BranchForm(forms.ModelForm):
    phone = forms.CharField(required=False, validators=[phone_validator], widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Branch
        fields = ['branch_name', 'phone', 'address', 'city', 'state', 'country', 'is_active']
        widgets = {
            'branch_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
        }


class TableForm(forms.ModelForm):
    class Meta:
        model = RestaurantTable
        fields = ['branch', 'table_number', 'is_active']
        widgets = {
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'table_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        restaurant = kwargs.pop('restaurant', None)
        super().__init__(*args, **kwargs)
        self.fields['branch'].queryset = Branch.objects.none()
        if restaurant:
            self.fields['branch'].queryset = Branch.objects.filter(restaurant=restaurant)

    def clean(self):
        cleaned = super().clean()
        branch = cleaned.get('branch')
        table_number = cleaned.get('table_number')
        if branch and table_number:
            qs = RestaurantTable.objects.filter(branch=branch, table_number=table_number)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(_('Table number must be unique within the branch.'))
        return cleaned
