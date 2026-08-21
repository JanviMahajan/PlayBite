from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from accounts.views import StaffRequiredMixin
from .models import Coupon, Redemption
from django.utils import timezone
from .services.redeemer import (
    coupon_code_from_payload,
    normalize_coupon_code,
    redeem_coupon,
    validate_qr_token,
)
from restaurants.models import Branch
from django.contrib import messages


class StaffPortalView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    template_name = 'coupons/staff_portal.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # basic widgets
        restaurant = getattr(self.request.user, 'restaurant', None)
        today = timezone.localdate()
        if restaurant:
            ctx['today_redemptions'] = restaurant.coupons.filter(redemption__redeemed_at__date=today).count()
            ctx['active_coupons'] = restaurant.coupons.filter(status=Coupon.Status.ACTIVE).count()
            ctx['pending_coupons'] = restaurant.coupons.filter(status=Coupon.Status.PENDING).count()
        return ctx


class RedeemScanView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    template_name = 'coupons/redeem_scan.html'


class RedeemManualView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    template_name = 'coupons/redeem_manual.html'

    def post(self, request, *args, **kwargs):
        code = request.POST.get('code')
        branch_id = request.POST.get('branch')
        branch = None
        if branch_id:
            branch = get_object_or_404(Branch, pk=branch_id, restaurant__owner=self.request.user)
        success, obj = redeem_coupon(user=request.user, coupon_code=code, branch=branch, device=request.META.get('HTTP_USER_AGENT','')[:255], ip_address=request.META.get('REMOTE_ADDR'))
        if success:
            messages.success(request, 'Coupon redeemed successfully.')
            return redirect('coupons_staff:staff_result', pk=obj.pk)
        else:
            messages.error(request, f'Redemption failed: {obj}')
            return redirect('coupons_staff:staff_manual')


class StaffResultView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    template_name = 'coupons/redeem_result.html'

    def get(self, request, pk):
        redemption = get_object_or_404(Redemption, pk=pk)
        return render(request, self.template_name, {'redemption': redemption})


class RedemptionHistoryView(LoginRequiredMixin, StaffRequiredMixin, ListView):
    template_name = 'coupons/redemption_history.html'
    context_object_name = 'redemptions'
    paginate_by = 40

    def get_queryset(self):
        # restrict to restaurant
        restaurant = getattr(self.request.user, 'restaurant', None)
        qs = Redemption.objects.select_related('coupon','coupon__reward','redeemed_by')
        if restaurant:
            qs = qs.filter(coupon__restaurant=restaurant)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(coupon__coupon_code__icontains=q)
        return qs.order_by('-redeemed_at')


# API endpoint for scanner: validate token or code and return JSON
from django.http import JsonResponse

class ScannerValidateAPI(View):
    def post(self, request):
        data = request.POST
        token = data.get('token')
        code = data.get('code')
        branch_id = data.get('branch')
        branch = None
        if branch_id:
            try:
                branch = Branch.objects.get(pk=branch_id, restaurant__owner=request.user)
            except Exception:
                branch = None
        # Determine coupon
        if token:
            payload = validate_qr_token(token)
            if not payload:
                return JsonResponse({'ok': False, 'reason': 'invalid_token'})
            code = coupon_code_from_payload(payload)
        else:
            code = normalize_coupon_code(code)
        if not code:
            return JsonResponse({'ok': False, 'reason': 'no_code'})
        try:
            coupon = Coupon.objects.get(coupon_code=code)
        except Coupon.DoesNotExist:
            return JsonResponse({'ok': False, 'reason': 'not_found'})
        coupon.mark_active_if_needed()
        # basic checks
        if branch and coupon.branch and coupon.branch.pk != branch.pk:
            return JsonResponse({'ok': False, 'reason': 'branch_mismatch'})
        if coupon.status == Coupon.Status.PENDING:
            return JsonResponse({'ok': False, 'reason': 'pending', 'valid_from': coupon.valid_from.isoformat() if coupon.valid_from else None})
        if coupon.status == Coupon.Status.EXPIRED:
            return JsonResponse({'ok': False, 'reason': 'expired', 'expiry': coupon.expiry_at.isoformat() if coupon.expiry_at else None})
        if coupon.status == Coupon.Status.REDEEMED:
            red = getattr(coupon, 'redemption', None)
            return JsonResponse({'ok': False, 'reason': 'already_redeemed', 'redeemed_at': red.redeemed_at.isoformat() if red and red.redeemed_at else None})
        # check active window
        now = timezone.now()
        if not coupon.valid_from or not coupon.expiry_at or not (coupon.valid_from <= now <= coupon.expiry_at):
            return JsonResponse({'ok': False, 'reason': 'not_active'})
        # if all good, return coupon summary
        return JsonResponse({'ok': True, 'coupon': {'code': coupon.coupon_code, 'reward': coupon.reward.title, 'customer': coupon.customer.full_name, 'generated_at': coupon.generated_at.isoformat(), 'valid_from': coupon.valid_from.isoformat() if coupon.valid_from else None, 'expiry_at': coupon.expiry_at.isoformat() if coupon.expiry_at else None}})


class ScannerRedeemAPI(View):
    def post(self, request):
        data = request.POST
        token = data.get('token')
        code = data.get('code')
        branch_id = data.get('branch')
        branch = None
        if branch_id:
            try:
                branch = Branch.objects.get(pk=branch_id, restaurant__owner=request.user)
            except Exception:
                branch = None
        success, obj = redeem_coupon(user=request.user, coupon_code=code, qr_token=token, branch=branch, device=request.META.get('HTTP_USER_AGENT','')[:255], ip_address=request.META.get('REMOTE_ADDR'))
        if success:
            # return redemption id
            return JsonResponse({'ok': True, 'redemption_id': obj.pk})
        else:
            return JsonResponse({'ok': False, 'reason': obj})
