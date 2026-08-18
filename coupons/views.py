from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin

from accounts.views import OwnerRequiredMixin
from .models import Reward, Coupon
from .forms import RewardForm


class RewardListView(LoginRequiredMixin, OwnerRequiredMixin, ListView):
    model = Reward
    template_name = 'coupons/reward_list.html'
    context_object_name = 'rewards'
    paginate_by = 12

    def get_queryset(self):
        qs = Reward.objects.filter(restaurant__owner=self.request.user).order_by('-created_at')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(title__icontains=q)
        return qs


class RewardCreateView(LoginRequiredMixin, OwnerRequiredMixin, CreateView):
    model = Reward
    form_class = RewardForm
    template_name = 'coupons/reward_form.html'
    success_url = reverse_lazy('coupons:reward_list')

    def form_valid(self, form):
        form.instance.restaurant = get_object_or_404(self.request.user.restaurant.__class__, owner=self.request.user)
        response = super().form_valid(form)
        messages.success(self.request, 'Reward created.')
        return response

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['restaurant'] = getattr(self.request.user, 'restaurant', None)
        return kwargs


class RewardUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Reward
    form_class = RewardForm
    template_name = 'coupons/reward_form.html'
    success_url = reverse_lazy('coupons:reward_list')

    def get_queryset(self):
        return Reward.objects.filter(restaurant__owner=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Reward updated.')
        return super().form_valid(form)


class RewardDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = Reward
    template_name = 'coupons/reward_confirm_delete.html'
    success_url = reverse_lazy('coupons:reward_list')

    def get_queryset(self):
        return Reward.objects.filter(restaurant__owner=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Reward deleted.')
        return super().delete(request, *args, **kwargs)


class RewardToggleActiveView(LoginRequiredMixin, OwnerRequiredMixin, View):
    def post(self, request, pk):
        reward = get_object_or_404(Reward, pk=pk, restaurant__owner=request.user)
        reward.is_active = not reward.is_active
        reward.save(update_fields=['is_active', 'updated_at'])
        messages.success(request, 'Reward activated.' if reward.is_active else 'Reward deactivated.')
        return redirect('coupons:reward_list')


class RewardDuplicateView(LoginRequiredMixin, OwnerRequiredMixin, View):
    def post(self, request, pk):
        reward = get_object_or_404(Reward, pk=pk, restaurant__owner=request.user)
        reward.pk = None
        reward.title = reward.title + ' (Copy)'
        reward.is_active = False
        reward.save()
        messages.success(request, 'Reward duplicated.')
        return redirect('coupons:reward_list')


class CouponListView(LoginRequiredMixin, OwnerRequiredMixin, ListView):
    model = Coupon
    template_name = 'coupons/coupon_list.html'
    context_object_name = 'coupons'
    paginate_by = 20

    def get_queryset(self):
        return Coupon.objects.filter(restaurant__owner=self.request.user).select_related('reward','customer').order_by('-generated_at')


# Simple owner dashboard summary
class CouponsDashboardView(LoginRequiredMixin, OwnerRequiredMixin, TemplateView):
    template_name = 'coupons/coupons_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        restaurant = getattr(self.request.user, 'restaurant', None)
        if restaurant:
            ctx['total'] = restaurant.coupons.count()
            ctx['pending'] = restaurant.coupons.filter(status=Coupon.Status.PENDING).count()
            ctx['active'] = restaurant.coupons.filter(status=Coupon.Status.ACTIVE).count()
            ctx['expired'] = restaurant.coupons.filter(status=Coupon.Status.EXPIRED).count()
            ctx['redeemed'] = restaurant.coupons.filter(status=Coupon.Status.REDEEMED).count()
        return ctx
