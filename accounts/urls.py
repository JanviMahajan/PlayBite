from django.urls import path
from django.views.generic import RedirectView
from django.urls import reverse_lazy

from .views import (
    OwnerDashboardView,
    OwnerLoginView,
    OwnerLogoutView,
    OwnerPinGateView,
    OwnerPasswordResetCompleteView,
    OwnerPasswordResetConfirmView,
    OwnerPasswordResetDoneView,
    OwnerPasswordResetView,
    OwnerRegisterView,
)

app_name = 'accounts'

urlpatterns = [
    path('', RedirectView.as_view(url=reverse_lazy('accounts:login')), name='index'),
    path('access/', OwnerPinGateView.as_view(), name='pin_gate'),
    path('register/', OwnerRegisterView.as_view(), name='register'),
    path('login/', OwnerLoginView.as_view(), name='login'),
    path('logout/', OwnerLogoutView.as_view(), name='logout'),
    path('dashboard/', OwnerDashboardView.as_view(), name='dashboard'),
    path('password-reset/', OwnerPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', OwnerPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', OwnerPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset-complete/', OwnerPasswordResetCompleteView.as_view(), name='password_reset_complete'),
]
