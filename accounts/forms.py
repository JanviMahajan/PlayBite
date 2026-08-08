from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class OwnerRegistrationForm(forms.ModelForm):
    restaurant_name = forms.CharField(
        max_length=255,
        required=True,
        label=_('Restaurant Name'),
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your restaurant or café name'}),
    )
    password1 = forms.CharField(
        label=_('Password'),
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class': 'form-control'}),
    )
    password2 = forms.CharField(
        label=_('Confirm Password'),
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class': 'form-control'}),
    )

    class Meta:
        model = User
        fields = ['full_name', 'email']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'John Doe'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'owner@example.com'}),
        }
        labels = {
            'full_name': _('Full Name'),
            'email': _('Email Address'),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_('An account with this email already exists.'))
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(_('The two password fields did not match.'))
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.role = User.Role.OWNER
        user.is_active = True
        if commit:
            user.save()
        return user


class OwnerAuthenticationForm(AuthenticationForm):
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        label=_('Remember me'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = _('Email Address')
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'owner@example.com', 'autocomplete': 'email'})
        self.fields['password'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Password', 'autocomplete': 'current-password'})


class OwnerPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'owner@example.com', 'autocomplete': 'email'})


class OwnerSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Enter a new password', 'autocomplete': 'new-password'})
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirm the new password', 'autocomplete': 'new-password'})
