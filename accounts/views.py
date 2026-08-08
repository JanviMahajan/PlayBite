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
from django.shortcuts import redirect
from django.urls import reverse_lazy
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


class OwnerRegisterView(FormView):
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


class OwnerLoginView(LoginView):
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
