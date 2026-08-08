from django.views.generic import TemplateView
from django.views import View
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import datetime
import csv

from .services import AnalyticsService

# Guarded access mixin (owners and staff)
class AnalyticsAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        user = request.user
        # allow owners and staff (owner or staff role attributes on user)
        is_owner = getattr(user, 'role', None) == 'OWNER' or getattr(user, 'is_owner', False)
        is_staff_role = getattr(user, 'role', None) == 'STAFF' or user.is_staff
        is_super = user.is_superuser
        if not (is_owner or is_staff_role or is_super):
            return HttpResponseForbidden('You do not have access to analytics')
        return super().dispatch(request, *args, **kwargs)

class AnalyticsDashboardView(AnalyticsAccessMixin, TemplateView):
    template_name = 'analytics/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # initial range: last 7 days
        end = timezone.localdate()
        start = end - timezone.timedelta(days=6)
        restaurant = getattr(self.request.user, 'restaurant', None)
        ctx['restaurant'] = restaurant
        ctx['start_date'] = start.isoformat()
        ctx['end_date'] = end.isoformat()
        return ctx

class AnalyticsOverviewAPI(AnalyticsAccessMixin, View):
    def get(self, request):
        restaurant = getattr(request.user, 'restaurant', None)
        if not restaurant:
            return JsonResponse({'ok': False, 'error': 'no_restaurant'})
        s = request.GET.get('start')
        e = request.GET.get('end')
        branch = request.GET.get('branch')
        game = request.GET.get('game')
        start = datetime.fromisoformat(s).date() if s else None
        end = datetime.fromisoformat(e).date() if e else None
        svc = AnalyticsService(restaurant, start_date=start, end_date=end)
        return JsonResponse({'ok': True, 'kpis': svc.kpis()})

class AnalyticsChartAPI(AnalyticsAccessMixin, View):
    def get(self, request, chart):
        restaurant = getattr(request.user, 'restaurant', None)
        if not restaurant:
            return JsonResponse({'ok': False, 'error': 'no_restaurant'})
        s = request.GET.get('start')
        e = request.GET.get('end')
        start = datetime.fromisoformat(s).date() if s else None
        end = datetime.fromisoformat(e).date() if e else None
        svc = AnalyticsService(restaurant, start_date=start, end_date=end)
        if chart == 'daily_scans':
            data = svc.daily_scans()
        elif chart == 'daily_games':
            data = svc.daily_games()
        elif chart == 'popular_games':
            data = svc.most_popular_games()
        elif chart == 'device_breakdown':
            data = svc.device_breakdown()
        else:
            data = {}
        return JsonResponse({'ok': True, 'data': data})

class AnalyticsExportView(AnalyticsAccessMixin, View):
    def get(self, request):
        # support CSV export of daily KPIs for date range
        restaurant = getattr(request.user, 'restaurant', None)
        if not restaurant:
            return HttpResponseForbidden('No restaurant')
        s = request.GET.get('start')
        e = request.GET.get('end')
        start = datetime.fromisoformat(s).date() if s else None
        end = datetime.fromisoformat(e).date() if e else None
        svc = AnalyticsService(restaurant, start_date=start, end_date=end)
        # build CSV rows: date, scans, games, coupons_generated, coupons_redeemed
        daily_scans = {d['date']: d['count'] for d in svc.daily_scans()}
        daily_games = {d['date']: d['count'] for d in svc.daily_games()}
        # dates iterate from start to end
        if not start or not end:
            return HttpResponse('Provide start and end', status=400)
        rows = []
        cur = start
        while cur <= end:
            date_s = cur.isoformat()
            rows.append({
                'date': date_s,
                'scans': daily_scans.get(date_s, 0),
                'games': daily_games.get(date_s, 0),
            })
            cur = cur + timezone.timedelta(days=1)
        # stream CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="analytics_{start.isoformat()}_{end.isoformat()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['date','scans','games'])
        for r in rows:
            writer.writerow([r['date'], r['scans'], r['games']])
        return response
