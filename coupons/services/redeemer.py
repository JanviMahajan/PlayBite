from django.db import transaction
from django.utils import timezone
from django.core import signing

from coupons.models import Coupon, Redemption


def validate_qr_token(token):
    try:
        payload = signing.loads(token)
        return payload
    except Exception:
        return None


@transaction.atomic
def redeem_coupon(user, coupon_code=None, qr_token=None, branch=None, device=None, ip_address=None):
    """Attempt to redeem coupon by coupon_code or signed qr_token.
    Returns (success:bool, obj_or_reason)
    """
    # Resolve coupon
    coupon = None
    if qr_token:
        payload = validate_qr_token(qr_token)
        if not payload:
            return False, 'invalid_token'
        code = payload.get('coupon_code')
        try:
            coupon = Coupon.objects.select_for_update().get(coupon_code=code)
        except Coupon.DoesNotExist:
            return False, 'not_found'
    elif coupon_code:
        try:
            coupon = Coupon.objects.select_for_update().get(coupon_code=coupon_code)
        except Coupon.DoesNotExist:
            return False, 'not_found'
    else:
        return False, 'no_identifier'

    # Coupons are created as PENDING and become active at the next calendar
    # day's validity boundary. Synchronize the stored status while the coupon
    # row is locked so a customer-facing "Ready to Use" coupon can redeem.
    coupon.mark_active_if_needed()

    # Validate ownership and status
    # coupon.restaurant must match branch.restaurant if branch provided
    if branch and coupon.branch and coupon.branch.pk != branch.pk:
        return False, 'branch_mismatch'

    # status checks
    if coupon.status == Coupon.Status.PENDING:
        return False, 'pending'
    if coupon.status == Coupon.Status.EXPIRED:
        return False, 'expired'
    if coupon.status == Coupon.Status.REDEEMED:
        return False, 'already_redeemed'

    # ensure within validity window
    now = timezone.now()
    if not coupon.valid_from or not coupon.expiry_at or not (coupon.valid_from <= now <= coupon.expiry_at):
        return False, 'not_active'

    # perform redemption
    redemption = Redemption.objects.create(coupon=coupon)
    redemption.mark_redeemed(user=user, branch=branch, device=device, ip=ip_address)

    # update coupon
    coupon.status = Coupon.Status.REDEEMED
    coupon.redemption_count = (coupon.redemption_count or 0) + 1
    coupon.save(update_fields=['status', 'redemption_count'])

    return True, redemption
