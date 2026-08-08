from django.urls import path

from . import views

app_name = 'restaurants'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('restaurant/profile/', views.RestaurantProfileView.as_view(), name='restaurant_profile'),
    path('restaurant/profile/edit/', views.RestaurantProfileEditView.as_view(), name='restaurant_profile_edit'),

    path('branches/', views.BranchListView.as_view(), name='branch_list'),
    path('branches/create/', views.BranchCreateView.as_view(), name='branch_create'),
    path('branches/<int:pk>/edit/', views.BranchUpdateView.as_view(), name='branch_edit'),
    path('branches/<int:pk>/delete/', views.BranchDeleteView.as_view(), name='branch_delete'),

    path('tables/', views.TableListView.as_view(), name='table_list'),
    path('tables/create/', views.TableCreateView.as_view(), name='table_create'),
    path('tables/<int:pk>/edit/', views.TableUpdateView.as_view(), name='table_edit'),
    path('tables/<int:pk>/delete/', views.TableDeleteView.as_view(), name='table_delete'),
    path('tables/<int:pk>/toggle/', views.TableToggleActiveView.as_view(), name='table_toggle'),

    # QR management
    path('qr/', views.QRListView.as_view(), name='qr_list'),
    path('qr/<int:pk>/', views.QRDetailView.as_view(), name='qr_detail'),
    path('qr/download/png/<int:pk>/', views.QRDownloadPNGView.as_view(), name='qr_download_png'),
    path('qr/download/pdf/<int:pk>/', views.QRDownloadPDFView.as_view(), name='qr_download_pdf'),
    path('qr/regenerate/<int:pk>/', views.QRRegenerateView.as_view(), name='qr_regenerate'),
]
