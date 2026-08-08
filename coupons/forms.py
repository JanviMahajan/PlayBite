from django import forms
from .models import Reward
from games.models import Game


class RewardForm(forms.ModelForm):
    class Meta:
        model = Reward
        fields = ['title', 'description', 'reward_type', 'reward_value', 'minimum_score', 'game_eligibility', 'eligible_games', 'start_date', 'end_date', 'coupon_valid_days', 'max_daily_redemptions', 'max_total_redemptions', 'is_active']
        widgets = {
            'start_date': forms.DateInput(attrs={'type':'date'}),
            'end_date': forms.DateInput(attrs={'type':'date'}),
            'eligible_games': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        restaurant = kwargs.pop('restaurant', None)
        super().__init__(*args, **kwargs)
        # limit eligible_games to games in DB
        self.fields['eligible_games'].queryset = Game.objects.filter(is_active=True)
        if not self.instance.pk:
            # defaults
            self.initial.setdefault('coupon_valid_days', 7)
