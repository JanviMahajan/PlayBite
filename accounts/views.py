import hmac
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import (
    LoginView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
    redirect_to_login,
)
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import FormView, TemplateView

from restaurants.models import Restaurant

from .forms import (
    OwnerAuthenticationForm,
    OwnerPasswordResetForm,
    OwnerRegistrationForm,
    OwnerSetPasswordForm,
)

User = get_user_model()

OWNER_PIN_SESSION_KEY = 'owner_pin_verified'


class OwnerPinRequiredMixin:
    """Require the shared owner-entry PIN once per browser session."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated or request.session.get(OWNER_PIN_SESSION_KEY):
            return super().dispatch(request, *args, **kwargs)
        gate_url = f"{reverse_lazy('accounts:pin_gate')}?{urlencode({'next': request.get_full_path()})}"
        return redirect(gate_url)


class OwnerPinGateView(View):
    template_name = 'accounts/pin_gate.html'

    @staticmethod
    def _safe_next(request):
        candidate = request.POST.get('next') or request.GET.get('next')
        allowed_paths = {str(reverse_lazy('accounts:login')), str(reverse_lazy('accounts:register'))}
        if (
            candidate
            and urlsplit(candidate).path in allowed_paths
            and url_has_allowed_host_and_scheme(candidate, allowed_hosts={request.get_host()})
        ):
            return candidate
        return str(reverse_lazy('accounts:login'))

    def get(self, request):
        if request.user.is_authenticated or request.session.get(OWNER_PIN_SESSION_KEY):
            return redirect(self._safe_next(request))
        return render(request, self.template_name, {'next': self._safe_next(request)})

    def post(self, request):
        entered_pin = request.POST.get('pin', '').strip()
        configured_pin = settings.OWNER_ACCESS_PIN
        if len(entered_pin) == 4 and entered_pin.isdigit() and hmac.compare_digest(entered_pin, configured_pin):
            request.session[OWNER_PIN_SESSION_KEY] = True
            request.session.set_expiry(0)
            return redirect(self._safe_next(request))
        return render(request, self.template_name, {
            'next': self._safe_next(request),
            'error': 'Incorrect PIN. Please try again.',
        }, status=400)


class OwnerRequiredMixin(UserPassesTestMixin):
    login_url = reverse_lazy('accounts:login')
    permission_denied_message = 'You do not have permission to access this page.'

    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_owner or self.request.user.is_super_admin
        )

    def handle_no_permission(self):
        return redirect_to_login(self.request.get_full_path(), self.get_login_url(), self.get_redirect_field_name())


class StaffRequiredMixin(UserPassesTestMixin):
    login_url = reverse_lazy('accounts:login')
    permission_denied_message = 'You do not have permission to access this page.'

    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.role == User.Role.STAFF or self.request.user.is_owner or self.request.user.is_super_admin
        )

    def handle_no_permission(self):
        return redirect_to_login(self.request.get_full_path(), self.get_login_url(), self.get_redirect_field_name())


class OwnerRegisterView(OwnerPinRequiredMixin, FormView):
    template_name = 'accounts/register.html'
    form_class = OwnerRegistrationForm
    success_url = reverse_lazy('accounts:dashboard')

    def form_valid(self, form):
        user = form.save()
        Restaurant.objects.create(
            owner=user,
            restaurant_name=form.cleaned_data['restaurant_name'],
            email=user.email,
        )
        login(self.request, user)
        messages.success(self.request, 'Welcome to PlayBite! Your restaurant owner account is ready.')
        return super().form_valid(form)


class OwnerLoginView(OwnerPinRequiredMixin, LoginView):
    template_name = 'accounts/login.html'
    authentication_form = OwnerAuthenticationForm
    redirect_authenticated_user = True
    next_page = reverse_lazy('accounts:dashboard')

    def form_valid(self, form):
        remember_me = form.cleaned_data.get('remember_me')
        if not remember_me:
            self.request.session.set_expiry(0)
        else:
            self.request.session.set_expiry(None)
        messages.success(self.request, 'Welcome back!')
        return super().form_valid(form)


class OwnerLogoutView(View):
    def dispatch(self, request, *args, **kwargs):
        logout(request)
        messages.success(request, 'You have been logged out successfully.')
        return redirect('accounts:login')


class OwnerPasswordResetView(PasswordResetView):
    template_name = 'accounts/password_reset.html'
    success_url = reverse_lazy('accounts:password_reset_done')
    email_template_name = 'accounts/password_reset_email.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    form_class = OwnerPasswordResetForm

    def form_valid(self, form):
        messages.success(self.request, 'If an account exists for that email, reset instructions have been sent.')
        return super().form_valid(form)


class OwnerPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class OwnerPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')
    form_class = OwnerSetPasswordForm


class OwnerPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'


class OwnerDashboardView(LoginRequiredMixin, OwnerRequiredMixin, TemplateView):
    template_name = 'accounts/dashboard_placeholder.html'
    login_url = reverse_lazy('accounts:login')
