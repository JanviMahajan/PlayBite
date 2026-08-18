from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from customer.models import Customer
from restaurants.models import Restaurant
from .forms import RewardForm
from .models import Coupon, Reward


class RewardFormTests(SimpleTestCase):
    def test_reward_value_is_not_an_owner_input(self):
        fields = RewardForm().fields
        self.assertNotIn('reward_value', fields)
        self.assertNotIn('start_date', fields)
        self.assertNotIn('end_date', fields)


class CustomerCouponTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        owner = get_user_model().objects.create_user('coupon-owner@example.com', raw_password='x')
        cls.restaurant = Restaurant.objects.create(owner=owner, restaurant_name='Token Cafe')
        cls.customer = Customer.objects.create(full_name='Coupon Guest', phone_number='+919876543210')
        cls.reward = Reward.objects.create(restaurant=cls.restaurant, title='Free Cookie')

    def make_coupon(self, *, status=Coupon.Status.PENDING, valid_from=None, expiry_at=None):
        now = timezone.now()
        coupon = Coupon.objects.create(
            customer=self.customer,
            restaurant=self.restaurant,
            reward=self.reward,
            status=status,
            valid_from=valid_from or now + timedelta(days=1),
            expiry_at=expiry_at or now + timedelta(days=8),
        )
        coupon.qr_token = signing.dumps({'coupon_code': coupon.coupon_code, 'ts': now.isoformat()})
        coupon.save(update_fields=['qr_token'])
        return coupon

    def view_url(self, coupon):
        return reverse('coupon_public:view', kwargs={'token': coupon.qr_token})

    def test_pending_coupon_view_reuses_same_coupon(self):
        coupon = self.make_coupon()
        before = Coupon.objects.count()
        response = self.client.get(self.view_url(coupon))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Available Tomorrow')
        self.assertContains(response, coupon.coupon_code)
        self.assertContains(response, 'WhatsApp')
        self.assertContains(response, 'Save Coupon')
        self.assertEqual(Coupon.objects.count(), before)
        coupon.refresh_from_db()
        self.assertEqual(coupon.status, Coupon.Status.PENDING)

    def test_active_redeemed_and_expired_statuses_are_server_derived(self):
        now = timezone.now()
        active = self.make_coupon(status=Coupon.Status.ACTIVE, valid_from=now - timedelta(days=1), expiry_at=now + timedelta(days=1))
        redeemed = self.make_coupon(status=Coupon.Status.REDEEMED, valid_from=now - timedelta(days=1), expiry_at=now + timedelta(days=1))
        expired = self.make_coupon(status=Coupon.Status.ACTIVE, valid_from=now - timedelta(days=3), expiry_at=now - timedelta(days=1))
        self.assertContains(self.client.get(self.view_url(active)), 'Ready to Use')
        self.assertContains(self.client.get(self.view_url(redeemed)), 'Already Redeemed')
        self.assertContains(self.client.get(self.view_url(expired)), 'Expired')

    def test_invalid_or_tampered_token_returns_safe_404(self):
        coupon = self.make_coupon()
        self.assertEqual(self.client.get('/coupon/view/not-a-token/').status_code, 404)
        self.assertEqual(self.client.get(self.view_url(coupon)[:-2] + 'x/').status_code, 404)

    def test_whatsapp_message_contains_private_url_but_not_phone(self):
        coupon = self.make_coupon()
        response = self.client.get(self.view_url(coupon))
        share_url = response.context['whatsapp_url']
        message = parse_qs(urlparse(share_url).query)['text'][0]
        self.assertIn(response.context['coupon_url'], message)
        self.assertIn(coupon.coupon_code, message)
        self.assertNotIn(self.customer.phone_number, message)

    def test_coupon_png_download_is_private_and_contains_no_phone_filename(self):
        coupon = self.make_coupon()
        url = reverse('coupon_public:download', kwargs={'token': coupon.qr_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertTrue(response.content.startswith(b'\x89PNG'))
        self.assertIn(coupon.coupon_code, response['Content-Disposition'])
        self.assertNotIn(self.customer.phone_number, response['Content-Disposition'])

    def test_arabic_coupon_page_and_share_message(self):
        coupon = self.make_coupon()
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'ar'
        response = self.client.get(self.view_url(coupon))
        self.assertContains(response, 'حفظ القسيمة')
        message = parse_qs(urlparse(response.context['whatsapp_url']).query)['text'][0]
        self.assertIn('عرض قسيمتي', message)
