from django.urls import path
from . import views

app_name = 'coupons'

urlpatterns = [
    path('rewards/', views.RewardListView.as_view(), name='reward_list'),
    path('rewards/create/', views.RewardCreateView.as_view(), name='reward_create'),
    path('rewards/<int:pk>/edit/', views.RewardUpdateView.as_view(), name='reward_edit'),
    path('rewards/<int:pk>/delete/', views.RewardDeleteView.as_view(), name='reward_delete'),
    path('rewards/<int:pk>/toggle/', views.RewardToggleActiveView.as_view(), name='reward_toggle'),
    path('rewards/<int:pk>/duplicate/', views.RewardDuplicateView.as_view(), name='reward_duplicate'),

    path('coupons/', views.CouponListView.as_view(), name='coupon_list'),
    path('', views.CouponsDashboardView.as_view(), name='coupons_dashboard'),
]
