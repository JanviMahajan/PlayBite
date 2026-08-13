"""
URL configuration for playbite project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from restaurants.views import PlayView, PlayOffersView, PlayInstructionsView, PlayStartView

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),
    path('', include('marketing.urls', namespace='marketing')),
    path('dashboard/', include('restaurants.urls', namespace='restaurants')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('play/<uuid:qr_slug>/', PlayView.as_view(), name='play'),
    path('play/<uuid:qr_slug>/offers/', PlayOffersView.as_view(), name='play_offers'),
    path('play/<uuid:qr_slug>/instructions/', PlayInstructionsView.as_view(), name='play_instructions'),
    path('play/<uuid:qr_slug>/start/', PlayStartView.as_view(), name='play_start'),
    path('games/', include('games.urls', namespace='games')),
    path('dashboard/rewards/', include('coupons.urls', namespace='coupons')),
    path('staff/', include(('coupons.staff_urls', 'coupons_staff'), namespace='coupons_staff')),
    path('dashboard/analytics/', include(('analytics.urls','analytics'), namespace='analytics')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
