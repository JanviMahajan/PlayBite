from django.urls import path

from . import public_views

app_name = 'coupon_public'

urlpatterns = [
    path('view/<str:token>/', public_views.CouponView.as_view(), name='view'),
    path('view/<str:token>/qr.png', public_views.CouponQRView.as_view(), name='qr'),
    path('view/<str:token>/save.png', public_views.CouponDownloadView.as_view(), name='download'),
]
