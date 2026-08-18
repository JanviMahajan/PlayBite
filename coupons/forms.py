from django import forms
from .models import Reward


class RewardForm(forms.ModelForm):
    class Meta:
        model = Reward
        fields = ['title', 'description', 'reward_type', 'coupon_valid_days', 'is_active']

    def __init__(self, *args, **kwargs):
        restaurant = kwargs.pop('restaurant', None)
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            # defaults
            self.initial.setdefault('coupon_valid_days', 7)
