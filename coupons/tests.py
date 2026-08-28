from datetime import timedelta
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from customer.models import Customer
from games.models import Game
from restaurants.models import Branch, Restaurant, RestaurantTable
from .forms import RewardForm
from .models import Coupon, Reward
from .services.redeemer import redeem_coupon


class RewardFormTests(SimpleTestCase):
    def test_reward_value_is_not_an_owner_input(self):
        fields = RewardForm().fields
        self.assertNotIn('reward_value', fields)
        self.assertIn('start_date', fields)
        self.assertIn('end_date', fields)
        self.assertNotIn('game_eligibility', fields)
        self.assertIn('eligible_games', fields)
        self.assertIn('applicable_tables', fields)
        self.assertNotIn('max_daily_redemptions', fields)
        self.assertNotIn('max_total_redemptions', fields)
        self.assertIn('is_active', fields)

    def test_end_date_cannot_precede_start_date(self):
        form = RewardForm(data={
            'title': 'Treat', 'description': '', 'reward_type': Reward.RewardType.FREE_ITEM,
            'start_date': '2026-08-20', 'end_date': '2026-08-19',
            'coupon_valid_days': 7, 'is_active': True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('end_date', form.errors)


class CustomerCouponTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('coupon-owner@example.com', raw_password='x')
        cls.restaurant = Restaurant.objects.create(owner=cls.owner, restaurant_name='Token Cafe')
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

    def test_owner_can_deactivate_and_reactivate_reward(self):
        self.client.force_login(self.owner)
        url = reverse('coupons:reward_toggle', args=[self.reward.pk])
        self.client.post(url)
        self.reward.refresh_from_db()
        self.assertFalse(self.reward.is_active)
        self.client.post(url)
        self.reward.refresh_from_db()
        self.assertTrue(self.reward.is_active)

    def test_owner_can_limit_reward_to_selected_games(self):
        game = Game.objects.get(slug='memory-match')
        form = RewardForm(data={
            'title': 'Memory Treat', 'description': 'Win memory match',
            'reward_type': Reward.RewardType.FREE_ITEM, 'coupon_valid_days': 7,
            'eligible_games': [game.pk], 'is_active': True,
        })
        self.assertTrue(form.is_valid(), form.errors)
        reward = form.save(commit=False)
        reward.restaurant = self.restaurant
        reward.save();form.save_m2m()
        self.assertEqual(reward.game_eligibility, Reward.GameEligibility.SPECIFIC)
        self.assertEqual(list(reward.eligible_games.values_list('pk', flat=True)), [game.pk])

    def test_no_selected_games_means_reward_applies_to_all(self):
        form = RewardForm(data={
            'title': 'Any Game Treat', 'description': '',
            'reward_type': Reward.RewardType.FREE_ITEM, 'coupon_valid_days': 7,
            'is_active': True,
        })
        self.assertTrue(form.is_valid(), form.errors)
        reward = form.save(commit=False)
        self.assertEqual(reward.game_eligibility, Reward.GameEligibility.ALL)

    def test_owner_selects_multiple_applicable_tables_on_reward(self):
        branch = Branch.objects.create(restaurant=self.restaurant, branch_name='Main')
        with patch.object(RestaurantTable, 'generate_qr_image'):
            table_one = RestaurantTable.objects.create(branch=branch, table_number='1')
            table_two = RestaurantTable.objects.create(branch=branch, table_number='2')

        self.client.force_login(self.owner)
        response = self.client.post(reverse('coupons:reward_create'), {
            'title': 'Visible Treat',
            'description': 'Available at unconfigured tables',
            'reward_type': Reward.RewardType.FREE_ITEM,
            'coupon_valid_days': 7,
            'is_active': True,
            'applicable_tables': [table_one.pk, table_two.pk],
        })

        self.assertRedirects(response, reverse('coupons:reward_list'))
        created = Reward.objects.get(title='Visible Treat')
        self.assertEqual(
            set(created.applicable_tables.values_list('pk', flat=True)),
            {table_one.pk, table_two.pk},
        )

        list_response = self.client.get(reverse('coupons:reward_list'))
        self.assertContains(list_response, 'Applicable Tables')
        self.assertContains(list_response, 'Table 1')
        self.assertContains(list_response, 'Table 2')

    def test_manual_redemption_redirects_to_staff_result(self):
        branch = Branch.objects.create(
            restaurant=self.restaurant, branch_name='Main', address='x',
            city='x', state='x', country='x',
        )
        now = timezone.now()
        coupon = self.make_coupon(
            status=Coupon.Status.ACTIVE,
            valid_from=now - timedelta(days=1),
            expiry_at=now + timedelta(days=1),
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('coupons_staff:staff_manual'),
            {'code': coupon.coupon_code, 'branch': branch.pk},
        )
        self.assertRedirects(
            response,
            reverse('coupons_staff:staff_result', kwargs={'pk': coupon.redemption.pk}),
        )
        coupon.refresh_from_db()
        self.assertEqual(coupon.status, Coupon.Status.REDEEMED)

    def test_pending_coupon_redeems_once_valid_from_has_passed(self):
        now = timezone.now()
        coupon = self.make_coupon(
            status=Coupon.Status.PENDING,
            valid_from=now - timedelta(minutes=1),
            expiry_at=now + timedelta(days=1),
        )
        success, redemption = redeem_coupon(
            self.owner,
            coupon_code=coupon.coupon_code,
        )
        self.assertTrue(success)
        self.assertEqual(redemption.coupon_id, coupon.pk)
        coupon.refresh_from_db()
        self.assertEqual(coupon.status, Coupon.Status.REDEEMED)

    def test_manual_redemption_normalizes_code_formatting(self):
        now = timezone.now()
        coupon = self.make_coupon(
            status=Coupon.Status.ACTIVE,
            valid_from=now - timedelta(minutes=1),
            expiry_at=now + timedelta(days=1),
        )
        entered = f'  {coupon.coupon_code.lower().replace("-", "–")}  '
        success, redemption = redeem_coupon(self.owner, coupon_code=entered)
        self.assertTrue(success)
        self.assertEqual(redemption.coupon_id, coupon.pk)

    def test_legacy_signed_token_code_key_still_redeems(self):
        now = timezone.now()
        coupon = self.make_coupon(
            status=Coupon.Status.ACTIVE,
            valid_from=now - timedelta(minutes=1),
            expiry_at=now + timedelta(days=1),
        )
        legacy_token = signing.dumps({'code': coupon.coupon_code})
        success, redemption = redeem_coupon(self.owner, qr_token=legacy_token)
        self.assertTrue(success)
        self.assertEqual(redemption.coupon_id, coupon.pk)

    def test_scanner_validation_activates_pending_coupon_in_valid_window(self):
        now = timezone.now()
        coupon = self.make_coupon(
            status=Coupon.Status.PENDING,
            valid_from=now - timedelta(minutes=1),
            expiry_at=now + timedelta(days=1),
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('coupons_staff:scanner_validate_api'),
            {'code': coupon.coupon_code},
        )
        self.assertTrue(response.json()['ok'])
        coupon.refresh_from_db()
        self.assertEqual(coupon.status, Coupon.Status.ACTIVE)

    def test_failed_manual_redemption_returns_to_manual_form(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('coupons_staff:staff_manual'),
            {'code': 'PB-NOTFOUND'},
        )
        self.assertRedirects(response, reverse('coupons_staff:staff_manual'))
