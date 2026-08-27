import csv
from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import TemplateView

from games.models import Game
from restaurants.models import Branch

from .services import AnalyticsService


class AnalyticsAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not (getattr(user, 'is_owner', False) or getattr(user, 'is_super_admin', False)):
            return HttpResponseForbidden('You do not have access to analytics')
        return super().dispatch(request, *args, **kwargs)

    def restaurant(self):
        return getattr(self.request.user, 'restaurant', None)

    def analytics_params(self):
        end_raw = self.request.GET.get('end', '')
        start_raw = self.request.GET.get('start', '')
        end = parse_date(end_raw) if end_raw else timezone.localdate()
        if end is None:
            raise ValueError('Invalid end date.')
        start = parse_date(start_raw) if start_raw else (end - timedelta(days=6))
        if start is None:
            raise ValueError('Invalid start date.')
        if start > end:
            raise ValueError('Start date must be on or before end date.')
        if (end - start).days > 366:
            raise ValueError('Date range cannot exceed 367 days.')

        restaurant = self.restaurant()
        branch = None
        branch_id = self.request.GET.get('branch')
        if branch_id:
            branch = Branch.objects.filter(pk=branch_id, restaurant=restaurant).first()
            if branch is None:
                raise ValueError('Invalid branch.')

        game = None
        game_id = self.request.GET.get('game')
        if game_id:
            game = Game.objects.filter(pk=game_id).first()
            if game is None:
                raise ValueError('Invalid game.')
        return start, end, branch, game

    def service(self):
        start, end, branch, game = self.analytics_params()
        return AnalyticsService(
            self.restaurant(), start_date=start, end_date=end, branch=branch, game=game,
        )


class AnalyticsDashboardView(AnalyticsAccessMixin, TemplateView):
    template_name = 'analytics/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        end = timezone.localdate()
        restaurant = self.restaurant()
        context.update({
            'restaurant': restaurant,
            'start_date': (end - timedelta(days=6)).isoformat(),
            'end_date': end.isoformat(),
            'branches': restaurant.branches.filter(is_active=True) if restaurant else [],
            'games': Game.objects.filter(is_active=True).order_by('name'),
        })
        return context


class AnalyticsOverviewAPI(AnalyticsAccessMixin, View):
    def get(self, request):
        if not self.restaurant():
            return JsonResponse({'ok': False, 'error': 'No restaurant is configured.'}, status=400)
        try:
            return JsonResponse({'ok': True, 'kpis': self.service().kpis()})
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)


class AnalyticsChartAPI(AnalyticsAccessMixin, View):
    charts = {
        'daily_scans': 'daily_scans',
        'daily_games': 'daily_games',
        'daily_coupons': 'daily_coupons',
        'daily_redemptions': 'daily_redemptions',
        'popular_games': 'most_popular_games',
        'device_breakdown': 'device_breakdown',
        'peak_hours': 'peak_hours',
    }

    def get(self, request, chart):
        if not self.restaurant():
            return JsonResponse({'ok': False, 'error': 'No restaurant is configured.'}, status=400)
        method = self.charts.get(chart)
        if not method:
            return JsonResponse({'ok': False, 'error': 'Unknown chart.'}, status=404)
        try:
            return JsonResponse({'ok': True, 'data': getattr(self.service(), method)()})
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)


class AnalyticsExportView(AnalyticsAccessMixin, View):
    def get(self, request):
        if not self.restaurant():
            return HttpResponseForbidden('No restaurant')
        try:
            service = self.service()
        except ValueError as exc:
            return HttpResponse(str(exc), status=400, content_type='text/plain')

        datasets = {
            'scans': {row['date']: row['count'] for row in service.daily_scans()},
            'games': {row['date']: row['count'] for row in service.daily_games()},
            'coupons_generated': {row['date']: row['count'] for row in service.daily_coupons()},
            'coupons_redeemed': {row['date']: row['count'] for row in service.daily_redemptions()},
        }
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="analytics_{service.start_date}_{service.end_date}.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(['date', *datasets.keys()])
        day = service.start_date
        while day <= service.end_date:
            key = day.isoformat()
            writer.writerow([key, *(dataset.get(key, 0) for dataset in datasets.values())])
            day += timedelta(days=1)
        return response
