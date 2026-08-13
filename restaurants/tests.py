from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from customer.models import Customer
from games.models import Gameplay
from .models import Branch, Restaurant, RestaurantTable


class CustomerEntryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        owner = get_user_model().objects.create_user('entry@example.com', raw_password='x', full_name='Owner')
        cls.restaurant = Restaurant.objects.create(owner=owner, restaurant_name='Entry Cafe')
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
