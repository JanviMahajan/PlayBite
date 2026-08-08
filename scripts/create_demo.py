import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'playbite.settings')
django.setup()

from django.contrib.auth import get_user_model
from restaurants.models import Restaurant, Branch, RestaurantTable
User = get_user_model()

u = User.objects.filter(email='owner@example.com').first()
if not u:
    print('Creating superuser owner@example.com')
    u = User.objects.create_superuser(email='owner@example.com', password='Passw0rd123', full_name='Demo Owner')
else:
    print('User exists:', u.pk)

r, created = Restaurant.objects.get_or_create(owner=u, defaults={'restaurant_name':'Demo Eatery','address':'123 Demo St','city':'Demo City','state':'Demo','country':'DemoLand'})
if created:
    print('Created restaurant', r.pk)
else:
    print('Restaurant exists', r.pk)

b, _ = Branch.objects.get_or_create(restaurant=r, branch_name='Main Branch', defaults={'address':'123 Demo St','city':'Demo City','state':'Demo','country':'DemoLand'})
print('Branch', b.pk)

t, _ = RestaurantTable.objects.get_or_create(branch=b, table_number='T1')
print('Table', t.pk)
