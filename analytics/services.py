from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone

from coupons.models import Coupon
from games.models import Gameplay
from restaurants.models import QRScan


class AnalyticsService:
    """Restaurant-scoped analytics with optional branch and game filters."""

    def __init__(self, restaurant, start_date=None, end_date=None, branch=None, game=None):
        self.restaurant = restaurant
        self.branch = branch
        self.game = game
        self.end_date = end_date or timezone.localdate()
        self.start_date = start_date or (self.end_date - timedelta(days=6))

    def _scan_queryset(self):
        qs = QRScan.objects.filter(
            table__branch__restaurant=self.restaurant,
            scanned_at__date__range=(self.start_date, self.end_date),
        )
        if self.branch:
            qs = qs.filter(table__branch=self.branch)
        return qs

    def _gameplay_queryset(self):
        qs = Gameplay.objects.filter(
            restaurant=self.restaurant,
            play_date__range=(self.start_date, self.end_date),
        )
        if self.branch:
            qs = qs.filter(restaurant_table__branch=self.branch)
        if self.game:
            qs = qs.filter(game=self.game)
        return qs

    def _coupon_queryset(self):
        qs = Coupon.objects.filter(
            restaurant=self.restaurant,
            generated_at__date__range=(self.start_date, self.end_date),
        )
        if self.branch:
            qs = qs.filter(Q(branch=self.branch) | Q(table__branch=self.branch))
        if self.game:
            qs = qs.filter(gameplay__game=self.game)
        return qs

    def _redemption_queryset(self):
        qs = Coupon.objects.filter(
            restaurant=self.restaurant,
            redemption__redeemed_at__date__range=(self.start_date, self.end_date),
        )
        if self.branch:
            qs = qs.filter(
                Q(redemption__branch=self.branch) | Q(branch=self.branch) | Q(table__branch=self.branch)
            )
        if self.game:
            qs = qs.filter(gameplay__game=self.game)
        return qs

    def _date_series(self, queryset, field):
        counts = {
            row['day']: row['count']
            for row in queryset.annotate(day=TruncDate(field))
            .values('day').annotate(count=Count('pk')).order_by('day')
        }
        output = []
        day = self.start_date
        while day <= self.end_date:
            output.append({'date': day.isoformat(), 'count': counts.get(day, 0)})
            day += timedelta(days=1)
        return output

    def total_qr_scans(self):
        return self._scan_queryset().count()

    def unique_customers(self):
        return self._gameplay_queryset().values('customer_id').distinct().count()

    def returning_customers(self):
        return self._gameplay_queryset().values('customer_id').annotate(
            visits=Count('play_date', distinct=True),
        ).filter(visits__gt=1).count()

    def games_played(self):
        return self._gameplay_queryset().count()

    def games_won(self):
        return self._gameplay_queryset().filter(result=Gameplay.Result.WON).count()

    def game_completion_rate(self):
        total = self.games_played()
        return round((self.games_won() / total) * 100, 2) if total else 0.0

    def coupons_generated(self):
        return self._coupon_queryset().count()

    def coupons_redeemed(self):
        return self._redemption_queryset().distinct().count()

    def redemption_rate(self):
        generated = self.coupons_generated()
        return round((self.coupons_redeemed() / generated) * 100, 2) if generated else 0.0

    def average_play_time(self):
        average = self._gameplay_queryset().exclude(play_time=None).aggregate(
            average=Avg('play_time'),
        )['average']
        return round(average.total_seconds(), 2) if average else None

    def kpis(self):
        return {
            'total_qr_scans': self.total_qr_scans(),
            'unique_customers': self.unique_customers(),
            'returning_customers': self.returning_customers(),
            'games_played': self.games_played(),
            'games_won': self.games_won(),
            'game_completion_rate': self.game_completion_rate(),
            'coupons_generated': self.coupons_generated(),
            'coupons_redeemed': self.coupons_redeemed(),
            'redemption_rate': self.redemption_rate(),
            'average_play_time': self.average_play_time(),
        }

    def daily_scans(self):
        return self._date_series(self._scan_queryset(), 'scanned_at')

    def daily_games(self):
        return self._date_series(self._gameplay_queryset(), 'created_at')

    def daily_coupons(self):
        return self._date_series(self._coupon_queryset(), 'generated_at')

    def daily_redemptions(self):
        return self._date_series(self._redemption_queryset(), 'redemption__redeemed_at')

    @staticmethod
    def _device_label(scan):
        value = f'{scan.device} {scan.user_agent}'.lower()
        if any(token in value for token in ('ipad', 'tablet', 'kindle')):
            return 'Tablet'
        if any(token in value for token in ('mobile', 'iphone', 'android')):
            return 'Mobile'
        if value.strip():
            return 'Desktop'
        return 'Unknown'

    def device_breakdown(self):
        counts = {}
        for scan in self._scan_queryset().only('device', 'user_agent'):
            label = self._device_label(scan)
            counts[label] = counts.get(label, 0) + 1
        return [
            {'device': label, 'count': count}
            for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    def most_popular_games(self, limit=5):
        rows = self._gameplay_queryset().values('game__name').annotate(
            count=Count('pk'),
        ).order_by('-count', 'game__name')[:limit]
        return [{'game': row['game__name'], 'count': row['count']} for row in rows]

    def peak_hours(self):
        rows = self._scan_queryset().annotate(hour=TruncHour('scanned_at')).values(
            'hour',
        ).annotate(count=Count('pk')).order_by('hour')
        counts = {row['hour'].hour: row['count'] for row in rows}
        return [{'hour': f'{hour:02d}:00', 'count': counts.get(hour, 0)} for hour in range(24)]
