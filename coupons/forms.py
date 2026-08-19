from django import forms
from .models import Reward


class RewardForm(forms.ModelForm):
    class Meta:
        model = Reward
        fields = [
            'title', 'description', 'reward_type', 'start_date', 'end_date',
            'coupon_valid_days', 'is_active',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        restaurant = kwargs.pop('restaurant', None)
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            # defaults
            self.initial.setdefault('coupon_valid_days', 7)

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get('start_date')
        end_date = cleaned.get('end_date')
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'End date must be on or after the start date.')
        return cleaned
