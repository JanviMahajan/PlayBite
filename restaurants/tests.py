from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from customer.models import Customer
from games.models import Gameplay
from .models import Branch, Restaurant, RestaurantTable
from .forms import BranchForm


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
        self.assertIn(gameplay.game.slug, {'burger-stack','order-rush','memory-match','pizza-slice'})
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
