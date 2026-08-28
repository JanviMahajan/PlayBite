from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from restaurants.models import Restaurant

User = get_user_model()


class OwnerAuthenticationTests(TestCase):
    def unlock_owner_access(self, next_url=None):
        return self.client.post(
            reverse('accounts:pin_gate'),
            {'pin': '8888', 'next': next_url or reverse('accounts:login')},
        )

    def test_login_and_registration_require_owner_pin(self):
        login_url = reverse('accounts:login')
        register_url = reverse('accounts:register')
        gate_url = reverse('accounts:pin_gate')

        self.assertRedirects(self.client.get(login_url), f'{gate_url}?next={login_url}')
        self.assertRedirects(self.client.get(register_url), f'{gate_url}?next={register_url}')

        rejected = self.client.post(gate_url, {'pin': '1234', 'next': register_url})
        self.assertEqual(rejected.status_code, 400)
        self.assertNotIn('owner_pin_verified', self.client.session)

        accepted = self.unlock_owner_access(register_url)
        self.assertRedirects(accepted, register_url)
        self.assertTrue(self.client.session['owner_pin_verified'])
        self.assertEqual(self.client.get(login_url).status_code, 200)
        self.assertEqual(self.client.get(register_url).status_code, 200)

    def test_owner_registration_creates_account_and_restaurant(self):
        self.unlock_owner_access(reverse('accounts:register'))
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
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('accounts:dashboard')}",
            fetch_redirect_response=False,
        )

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
