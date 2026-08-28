from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Reward


class RewardForm(forms.ModelForm):
    class Meta:
        model = Reward
        fields = [
            'title', 'description', 'reward_type', 'start_date', 'end_date',
            'coupon_valid_days', 'eligible_games', 'applicable_tables', 'is_active',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'eligible_games': forms.CheckboxSelectMultiple(),
            'applicable_tables': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        restaurant = kwargs.pop('restaurant', None)
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            # defaults
            self.initial.setdefault('coupon_valid_days', 7)
        self.fields['eligible_games'].queryset = self.fields['eligible_games'].queryset.filter(
            is_active=True,
        ).order_by('name')
        self.fields['eligible_games'].required = False
        self.fields['eligible_games'].label = 'Eligible games'
        self.fields['eligible_games'].help_text = 'Leave every game unchecked to make this reward available for all games.'
        self.fields['applicable_tables'].required = False
        self.fields['applicable_tables'].label = _('Applicable Tables')
        self.fields['applicable_tables'].help_text = _('Select one or more tables where customers can win this reward.')
        self.fields['applicable_tables'].queryset = self.fields['applicable_tables'].queryset.none()
        if restaurant:
            self.fields['applicable_tables'].queryset = self.fields['applicable_tables'].queryset.model.objects.filter(
                branch__restaurant=restaurant,
            ).select_related('branch').order_by('branch__branch_name', 'table_number')
        if self.instance.pk and self.instance.game_eligibility == Reward.GameEligibility.ALL:
            self.initial['eligible_games'] = []

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get('start_date')
        end_date = cleaned.get('end_date')
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'End date must be on or after the start date.')
        self.instance.game_eligibility = (
            Reward.GameEligibility.SPECIFIC
            if cleaned.get('eligible_games') else Reward.GameEligibility.ALL
        )
        return cleaned
