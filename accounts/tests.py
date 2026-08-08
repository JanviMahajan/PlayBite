from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from restaurants.models import Restaurant

User = get_user_model()


class OwnerAuthenticationTests(TestCase):
    def test_owner_registration_creates_account_and_restaurant(self):
        response = self.client.post(
            reverse('accounts:register'),
            {
                'full_name': 'Asha Patel',
                'email': 'asha@example.com',
                'restaurant_name': 'Spice & Smoke',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            },
        )

        self.assertRedirects(response, reverse('accounts:dashboard'))
        user = User.objects.get(email='asha@example.com')
        self.assertTrue(user.is_owner)
        self.assertTrue(user.check_password('StrongPass123!'))
        self.assertTrue(Restaurant.objects.filter(owner=user, restaurant_name='Spice & Smoke').exists())
        self.assertIn('_auth_user_id', self.client.session)

    def test_owner_dashboard_requires_owner_access(self):
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('accounts:dashboard')}")

        staff_user = User.objects.create_user(
            email='staff@example.com',
            password='StaffPass123!',
            full_name='Staff Member',
            role=User.Role.STAFF,
        )
        self.client.force_login(staff_user)
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_password_reset_flow_renders_done_page(self):
        User.objects.create_user(
            email='reset@example.com',
            password='ResetPass123!',
            full_name='Reset User',
            role=User.Role.OWNER,
        )

        response = self.client.post(reverse('accounts:password_reset'), {'email': 'reset@example.com'})
        self.assertRedirects(response, reverse('accounts:password_reset_done'))
