from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from coupons.models import Coupon, Redemption, Reward
from customer.models import Customer
from games.models import Game, Gameplay
from restaurants.models import Branch, QRScan, Restaurant, RestaurantTable

from .services import AnalyticsService


class AnalyticsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.owner = get_user_model().objects.create_user('analytics@example.com', raw_password='x')
        cls.restaurant = Restaurant.objects.create(owner=cls.owner, restaurant_name='Analytics Cafe')
        cls.branch_a = Branch.objects.create(restaurant=cls.restaurant, branch_name='A')
        cls.branch_b = Branch.objects.create(restaurant=cls.restaurant, branch_name='B')
        cls.table_a = RestaurantTable.objects.create(branch=cls.branch_a, table_number='1')
        cls.table_b = RestaurantTable.objects.create(branch=cls.branch_b, table_number='1')
        cls.game_a = Game.objects.create(name='Analytics Game A', slug='analytics-a', duration=timedelta(seconds=20))
        cls.game_b = Game.objects.create(name='Analytics Game B', slug='analytics-b', duration=timedelta(seconds=20))
        cls.customer_a = Customer.objects.create(full_name='A', phone_number='+910000000101')
        cls.customer_b = Customer.objects.create(full_name='B', phone_number='+910000000102')
        cls.reward = Reward.objects.create(restaurant=cls.restaurant, title='Treat')

        cls.scan_mobile = QRScan.objects.create(table=cls.table_a, user_agent='iPhone Mobile Safari')
        cls.scan_desktop = QRScan.objects.create(table=cls.table_b, user_agent='Macintosh Safari')
        cls.gameplay_a = Gameplay.objects.create(
            customer=cls.customer_a, restaurant=cls.restaurant, restaurant_table=cls.table_a,
            game=cls.game_a, play_date=cls.today, result=Gameplay.Result.WON,
            completed=True, play_time=timedelta(seconds=12),
        )
        cls.gameplay_b = Gameplay.objects.create(
            customer=cls.customer_b, restaurant=cls.restaurant, restaurant_table=cls.table_b,
            game=cls.game_b, play_date=cls.today, result=Gameplay.Result.LOST,
            completed=False, play_time=timedelta(seconds=20),
        )
        cls.coupon = Coupon.objects.create(
            customer=cls.customer_a, restaurant=cls.restaurant, branch=cls.branch_a,
            table=cls.table_a, reward=cls.reward, gameplay=cls.gameplay_a,
            status=Coupon.Status.REDEEMED,
        )
        cls.redemption = Redemption.objects.create(
            coupon=cls.coupon, redeemed_at=timezone.now(), redeemed_by=cls.owner,
            branch=cls.branch_a,
        )

        other_owner = get_user_model().objects.create_user('other-analytics@example.com', raw_password='x')
        other_restaurant = Restaurant.objects.create(owner=other_owner, restaurant_name='Other Cafe')
        other_branch = Branch.objects.create(restaurant=other_restaurant, branch_name='Other')
        other_table = RestaurantTable.objects.create(branch=other_branch, table_number='1')
        QRScan.objects.create(table=other_table, user_agent='Android Mobile')

    def setUp(self):
        self.client.force_login(self.owner)
        self.params = {'start': self.today.isoformat(), 'end': self.today.isoformat()}

    def test_service_kpis_are_real_and_restaurant_scoped(self):
        kpis = AnalyticsService(self.restaurant, self.today, self.today).kpis()
        self.assertEqual(kpis['total_qr_scans'], 2)
        self.assertEqual(kpis['unique_customers'], 2)
        self.assertEqual(kpis['games_played'], 2)
        self.assertEqual(kpis['games_won'], 1)
        self.assertEqual(kpis['game_completion_rate'], 50.0)
        self.assertEqual(kpis['coupons_generated'], 1)
        self.assertEqual(kpis['coupons_redeemed'], 1)
        self.assertEqual(kpis['average_play_time'], 16.0)

    def test_branch_and_game_filters_apply(self):
        service = AnalyticsService(
            self.restaurant, self.today, self.today,
            branch=self.branch_a, game=self.game_a,
        )
        self.assertEqual(service.total_qr_scans(), 1)
        self.assertEqual(service.games_played(), 1)
        self.assertEqual(service.coupons_generated(), 1)
        self.assertEqual(service.device_breakdown(), [{'device': 'Mobile', 'count': 1}])

    def test_daily_series_contains_zero_value_dates(self):
        service = AnalyticsService(
            self.restaurant, self.today - timedelta(days=2), self.today,
        )
        series = service.daily_scans()
        self.assertEqual(len(series), 3)
        self.assertEqual([row['count'] for row in series], [0, 0, 2])

    def test_overview_and_all_chart_apis(self):
        overview = self.client.get(reverse('analytics:api_overview'), self.params)
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.json()['kpis']['games_played'], 2)
        for chart in (
            'daily_scans', 'daily_games', 'daily_coupons', 'daily_redemptions',
            'popular_games', 'device_breakdown', 'peak_hours',
        ):
            response = self.client.get(reverse('analytics:api_chart', args=[chart]), self.params)
            self.assertEqual(response.status_code, 200, chart)
            self.assertTrue(response.json()['ok'])

    def test_invalid_dates_and_cross_restaurant_branch_are_rejected(self):
        invalid = self.client.get(reverse('analytics:api_overview'), {
            'start': self.today.isoformat(),
            'end': (self.today - timedelta(days=1)).isoformat(),
        })
        self.assertEqual(invalid.status_code, 400)
        malformed = self.client.get(reverse('analytics:api_overview'), {'start': 'not-a-date'})
        self.assertEqual(malformed.status_code, 400)
        other_branch = Branch.objects.exclude(restaurant=self.restaurant).first()
        cross_tenant = self.client.get(reverse('analytics:api_overview'), {
            **self.params, 'branch': other_branch.pk,
        })
        self.assertEqual(cross_tenant.status_code, 400)

    def test_csv_export_contains_complete_daily_metrics(self):
        response = self.client.get(reverse('analytics:export'), self.params)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('date,scans,games,coupons_generated,coupons_redeemed', content)
        self.assertIn(f'{self.today.isoformat()},2,2,1,1', content)

    def test_dashboard_renders_filters_and_chart_targets(self):
        response = self.client.get(reverse('analytics:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'All branches')
        self.assertContains(response, 'chart_daily_scans')
        self.assertContains(response, 'chart_peak_hours')
