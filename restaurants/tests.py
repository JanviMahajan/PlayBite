from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from customer.models import Customer
from coupons.models import Reward
from games.models import Gameplay
from .models import Branch, Restaurant, RestaurantTable
from .forms import BranchForm, TableForm


class CustomerEntryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('entry@example.com', raw_password='x', full_name='Owner')
        cls.restaurant = Restaurant.objects.create(owner=cls.owner, restaurant_name='Entry Cafe')
        cls.branch = Branch.objects.create(restaurant=cls.restaurant, branch_name='Main', address='x', city='x', state='x', country='x')
        with patch.object(RestaurantTable, 'generate_qr_image'):
            cls.table = RestaurantTable.objects.create(branch=cls.branch, table_number='1')

    def test_qr_identity_and_assignment_redirect(self):
        self.client.get(reverse('play', args=[self.table.qr_slug]))
        response = self.client.post(reverse('play_start', args=[self.table.qr_slug]), {'full_name':'Guest','phone_number':'+91 98765 43210'})
        self.assertEqual(response.status_code, 302)
        customer = Customer.objects.get(phone_number='+919876543210')
        gameplay = Gameplay.objects.get(customer=customer)
        self.assertIn(gameplay.game.slug, {'burger-stack','order-rush','memory-match','pizza-slice','tap-at-ten'})
        self.assertEqual(self.client.session['play_session']['gameplay_id'], gameplay.pk)

    def test_invalid_phone_is_rejected(self):
        response = self.client.post(reverse('play_start', args=[self.table.qr_slug]), {'full_name':'Guest','phone_number':'12'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Customer.objects.exists())

    def test_table_qr_url_uses_public_play_route(self):
        self.assertEqual(
            self.table.get_qr_url(),
            reverse('play', args=[self.table.qr_slug]),
        )

    def test_public_offers_match_gameplay_reward_availability(self):
        current = Reward.objects.create(restaurant=self.restaurant, title='Current', is_active=True)
        self.table.reward=current;self.table.save(update_fields=['reward','updated_at'])
        Reward.objects.create(
            restaurant=self.restaurant, title='Future', is_active=True,
            start_date=timezone.localdate() + timedelta(days=1),
        )
        Reward.objects.create(
            restaurant=self.restaurant, title='Expired', is_active=True,
            end_date=timezone.localdate() - timedelta(days=1),
        )
        response = self.client.get(reverse('play_offers', args=[self.table.qr_slug]))
        self.assertContains(response, current.title)
        self.assertNotContains(response, 'Future')
        self.assertNotContains(response, 'Expired')

    def test_qr_pages_render_dashboard_shell_once(self):
        self.client.force_login(self.owner)
        list_response = self.client.get(reverse('restaurants:qr_list'))
        with patch.object(RestaurantTable, 'generate_qr_image'):
            detail_response = self.client.get(reverse('restaurants:qr_detail', args=[self.table.pk]))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(list_response, 'dashboard-topnav', count=1)
        self.assertContains(list_response, 'dashboard-sidebar', count=1)
        self.assertContains(detail_response, 'dashboard-topnav', count=1)
        self.assertContains(detail_response, 'dashboard-sidebar', count=1)


class BranchFormTests(TestCase):
    def test_location_coordinates_are_not_owner_inputs(self):
        form = BranchForm()
        self.assertNotIn('latitude', form.fields)
        self.assertNotIn('longitude', form.fields)


class TableRewardOwnerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner_a=get_user_model().objects.create_user('table-a@example.com',raw_password='x')
        cls.owner_b=get_user_model().objects.create_user('table-b@example.com',raw_password='x')
        cls.restaurant_a=Restaurant.objects.create(owner=cls.owner_a,restaurant_name='Table Cafe A')
        cls.restaurant_b=Restaurant.objects.create(owner=cls.owner_b,restaurant_name='Table Cafe B')
        cls.branch_a=Branch.objects.create(restaurant=cls.restaurant_a,branch_name='Main A')
        cls.branch_b=Branch.objects.create(restaurant=cls.restaurant_b,branch_name='Main B')
        cls.reward_a=Reward.objects.create(restaurant=cls.restaurant_a,title='A Reward')
        cls.reward_b=Reward.objects.create(restaurant=cls.restaurant_b,title='B Reward')
        with patch.object(RestaurantTable,'generate_qr_image'):
            cls.table_a=RestaurantTable.objects.create(branch=cls.branch_a,table_number='A1',reward=cls.reward_a)
            cls.table_b=RestaurantTable.objects.create(branch=cls.branch_b,table_number='B1',reward=cls.reward_b)
            cls.table_unassigned=RestaurantTable.objects.create(branch=cls.branch_a,table_number='A2')

    def test_table_form_only_lists_rewards_from_the_owner_restaurant(self):
        form=TableForm(instance=self.table_a,restaurant=self.restaurant_a)
        self.assertIn(self.reward_a,form.fields['reward'].queryset)
        self.assertNotIn(self.reward_b,form.fields['reward'].queryset)

    def test_cross_restaurant_reward_assignment_is_rejected(self):
        form=TableForm(
            instance=self.table_a,
            restaurant=self.restaurant_a,
            data={'branch':self.branch_a.pk,'table_number':'A1','reward':self.reward_b.pk,'is_active':True},
        )
        self.assertFalse(form.is_valid())
        self.table_a.refresh_from_db()
        self.assertEqual(self.table_a.reward,self.reward_a)

    def test_owner_cannot_edit_another_owners_table(self):
        self.client.force_login(self.owner_a)
        response=self.client.get(reverse('restaurants:table_edit',args=[self.table_b.pk]))
        self.assertEqual(response.status_code,404)

    def test_table_list_displays_assigned_and_unconfigured_rewards(self):
        self.client.force_login(self.owner_a)
        response=self.client.get(reverse('restaurants:table_list'))
        self.assertContains(response,'A Reward')
        self.assertContains(response,'Not configured')


class DashboardStatsTests(TestCase):
    def test_dashboard_uses_owner_database_counts_and_links_rewards(self):
        owner = get_user_model().objects.create_user('stats@example.com', raw_password='x')
        restaurant = Restaurant.objects.create(owner=owner, restaurant_name='Stats Cafe')
        branch = Branch.objects.create(restaurant=restaurant, branch_name='Main')
        with patch.object(RestaurantTable, 'generate_qr_image'):
            RestaurantTable.objects.create(branch=branch, table_number='1')
        Reward.objects.create(restaurant=restaurant, title='Free Coffee')
        Reward.objects.create(restaurant=restaurant, title='Free Cookie')
        self.client.force_login(owner)
        response = self.client.get(reverse('restaurants:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['stats']['total_tables'], 1)
        self.assertEqual(response.context['stats']['active_branches'], 1)
        self.assertEqual(response.context['stats']['total_rewards'], 3)
        self.assertContains(response, reverse('coupons:reward_list'))

    def test_new_restaurant_gets_default_tap_at_ten_coffee_reward(self):
        owner = get_user_model().objects.create_user('coffee@example.com', raw_password='x')
        restaurant = Restaurant.objects.create(owner=owner, restaurant_name='Coffee Cafe')
        reward = restaurant.rewards.get(
            title='Free Coffee', game_eligibility=Reward.GameEligibility.SPECIFIC,
        )
        self.assertEqual(reward.reward_type, Reward.RewardType.FREE_BEVERAGE)
        self.assertTrue(reward.is_active)
        self.assertEqual(list(reward.eligible_games.values_list('slug', flat=True)), ['tap-at-ten'])
