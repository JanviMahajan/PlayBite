from datetime import datetime, timedelta
from django.db.models import Count, Avg, Sum, Q
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone

# Import models used for analytics
from restaurants.models import Restaurant, Branch, QRScan, RestaurantTable
from games.models import Gameplay, Game
from coupons.models import Coupon, Redemption, Reward

class AnalyticsService:
    def __init__(self, restaurant, start_date=None, end_date=None, branch=None, game=None):
        self.restaurant = restaurant
        self.branch = branch
        self.game = game
        today = timezone.localdate()
        if end_date:
            self.end_date = end_date
        else:
            self.end_date = today
        if start_date:
            self.start_date = start_date
        else:
            self.start_date = self.end_date - timedelta(days=6)

    def _base_filters(self):
        filters = Q()
        # QRScan and tables belong to restaurant
        filters &= Q(table__branch__restaurant=self.restaurant)
        if self.branch:
            filters &= Q(table__branch=self.branch)
        return filters

    def total_qr_scans(self):
        qs = QRScan.objects.filter(self._base_filters(), created_at__date__range=(self.start_date, self.end_date))
        return qs.count()

    def unique_customers(self):
        qs = Gameplay.objects.filter(restaurant=self.restaurant, created_at__date__range=(self.start_date, self.end_date))
        return qs.values('customer_id').distinct().count()

    def returning_customers(self):
        qs = Gameplay.objects.filter(restaurant=self.restaurant, created_at__date__range=(self.start_date, self.end_date))
        agg = qs.values('customer_id').annotate(plays=Count('pk')).filter(plays__gt=1)
        return agg.count()

    def games_played(self):
        qs = Gameplay.objects.filter(restaurant=self.restaurant, created_at__date__range=(self.start_date, self.end_date))
        if self.game:
            qs = qs.filter(game=self.game)
        return qs.count()

    def game_completion_rate(self):
        qs = Gameplay.objects.filter(restaurant=self.restaurant, created_at__date__range=(self.start_date, self.end_date))
        total = qs.count()
        if total == 0:
            return 0.0
        completed = qs.filter(status=Gameplay.Status.COMPLETED).count() if hasattr(Gameplay, 'Status') else qs.filter(completed=True).count()
        return round(100.0 * (completed / total), 2)

    def coupons_generated(self):
        qs = Coupon.objects.filter(restaurant=self.restaurant, generated_at__date__range=(self.start_date, self.end_date))
        return qs.count()

    def coupons_redeemed(self):
        qs = Coupon.objects.filter(restaurant=self.restaurant, redemption__redeemed_at__date__range=(self.start_date, self.end_date))
        return qs.count()

    def redemption_rate(self):
        gen = self.coupons_generated()
        if gen == 0:
            return 0.0
        red = self.coupons_redeemed()
        return round(100.0 * (red / gen), 2)

    def average_play_time(self):
        qs = Gameplay.objects.filter(restaurant=self.restaurant, created_at__date__range=(self.start_date, self.end_date))
        # assume Gameplay has completion_time_seconds or duration
        if hasattr(Gameplay, 'completion_time_seconds'):
            avg = qs.aggregate(avg=Avg('completion_time_seconds'))['avg']
        else:
            avg = qs.aggregate(avg=Avg('duration_seconds'))['avg'] if hasattr(Gameplay, 'duration_seconds') else None
        return round(avg,2) if avg else None

    def average_game_score(self):
        qs = Gameplay.objects.filter(restaurant=self.restaurant, created_at__date__range=(self.start_date, self.end_date))
        if hasattr(Gameplay, 'score'):
            avg = qs.aggregate(avg=Avg('score'))['avg']
            return round(avg,2) if avg is not None else None
        return None

    def kpis(self):
        return {
            'total_qr_scans': self.total_qr_scans(),
            'unique_customers': self.unique_customers(),
            'returning_customers': self.returning_customers(),
            'games_played': self.games_played(),
            'game_completion_rate': self.game_completion_rate(),
            'coupons_generated': self.coupons_generated(),
            'coupons_redeemed': self.coupons_redeemed(),
            'redemption_rate': self.redemption_rate(),
            'average_play_time': self.average_play_time(),
            'average_game_score': self.average_game_score(),
        }

    def daily_scans(self):
        qs = QRScan.objects.filter(self._base_filters(), created_at__date__range=(self.start_date, self.end_date))
        qs = qs.annotate(day=TruncDate('created_at')).values('day').annotate(count=Count('pk')).order_by('day')
        return [{'date': r['day'].isoformat(), 'count': r['count']} for r in qs]

    def daily_games(self):
        qs = Gameplay.objects.filter(restaurant=self.restaurant, created_at__date__range=(self.start_date, self.end_date))
        if self.game:
            qs = qs.filter(game=self.game)
        qs = qs.annotate(day=TruncDate('created_at')).values('day').annotate(count=Count('pk')).order_by('day')
        return [{'date': r['day'].isoformat(), 'count': r['count']} for r in qs]

    def device_breakdown(self):
        qs = QRScan.objects.filter(self._base_filters(), created_at__date__range=(self.start_date, self.end_date))
        # assume QRScan has device_type field
        if hasattr(QRScan, 'device_type'):
            agg = qs.values('device_type').annotate(count=Count('pk')).order_by('-count')
            return [{'device': r['device_type'] or 'Unknown', 'count': r['count']} for r in agg]
        return []

    def most_popular_games(self, limit=5):
        qs = Gameplay.objects.filter(restaurant=self.restaurant, created_at__date__range=(self.start_date, self.end_date))
        agg = qs.values('game__name').annotate(count=Count('pk')).order_by('-count')[:limit]
        return [{'game': r['game__name'], 'count': r['count']} for r in agg]
