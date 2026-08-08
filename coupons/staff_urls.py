from django.urls import path
from . import staff_views

app_name = 'coupons_staff'

urlpatterns = [
    path('', staff_views.StaffPortalView.as_view(), name='staff_portal'),
    path('redeem/scan/', staff_views.RedeemScanView.as_view(), name='staff_scan'),
    path('redeem/manual/', staff_views.RedeemManualView.as_view(), name='staff_manual'),
    path('redeem/result/<int:pk>/', staff_views.StaffResultView.as_view(), name='staff_result'),
    path('history/', staff_views.RedemptionHistoryView.as_view(), name='redemption_history'),
    path('api/validate/', staff_views.ScannerValidateAPI.as_view(), name='scanner_validate_api'),
    path('api/redeem/', staff_views.ScannerRedeemAPI.as_view(), name='scanner_redeem_api'),
]
