from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from games.models import Game
from .models import Branch, Restaurant, RestaurantTable


class PlayStartTests(TestCase):
    def test_play_now_serializes_database_duration(self):
        owner = get_user_model().objects.create_user(
            'owner@example.com', raw_password='password123', full_name='Owner'
        )
        restaurant = Restaurant.objects.create(owner=owner, restaurant_name='Cafe')
        branch = Branch.objects.create(
            restaurant=restaurant, branch_name='Main', address='x', city='x', state='x', country='x'
        )
        with patch.object(RestaurantTable, 'generate_qr_image'):
            table = RestaurantTable.objects.create(branch=branch, table_number='1')
        Game.objects.create(name='Memory Match', slug='memory-match', duration=timedelta(seconds=45))

        self.client.get(reverse('play', args=[table.qr_slug]))
        response = self.client.post(reverse('play_start', args=[table.qr_slug]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['game']['duration'], 45)
        self.assertEqual(self.client.session['play_session']['selected_game']['duration'], 45)
