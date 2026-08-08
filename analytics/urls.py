from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('', views.AnalyticsDashboardView.as_view(), name='dashboard'),
    path('api/overview/', views.AnalyticsOverviewAPI.as_view(), name='api_overview'),
    path('api/chart/<str:chart>/', views.AnalyticsChartAPI.as_view(), name='api_chart'),
    path('export/', views.AnalyticsExportView.as_view(), name='export'),
]
