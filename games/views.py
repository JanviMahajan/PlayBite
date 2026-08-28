import json
import logging

from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views import View

from coupons.services.generator import generate_coupon_for_gameplay
from coupons.services.presentation import public_coupon_url
from .models import Gameplay
from .services.gameplay import GAME_UI, start_gameplay, submit_gameplay

logger = logging.getLogger(__name__)


def _session_gameplay(request, slug=None):
    play_session = request.session.get('play_session') or {}
    gameplay_id = play_session.get('gameplay_id')
    customer_id = play_session.get('customer_id')
    if not gameplay_id or not customer_id:
        raise Http404('Game session not found.')
    queryset = Gameplay.objects.select_related(
        'game', 'restaurant', 'restaurant_table__branch', 'restaurant_table__reward', 'customer'
    )
    filters = {'pk': gameplay_id, 'customer_id': customer_id}
    if slug:
        filters['game__slug'] = slug
    try:
        return queryset.get(**filters)
    except Gameplay.DoesNotExist as exc:
        raise Http404('Game session not found.') from exc


class GamePageView(View):
    def get(self, request, slug):
        gameplay = _session_gameplay(request, slug)
        if (gameplay.result == Gameplay.Result.IN_PROGRESS and gameplay.deadline
                and timezone.now() > gameplay.deadline and not gameplay.submitted_at):
            gameplay, _, _ = submit_gameplay(gameplay.pk, gameplay.customer_id, False, {})
        coupon = gameplay.coupons.first()
        if gameplay.result == Gameplay.Result.WON and coupon is None:
            try:
                coupon = generate_coupon_for_gameplay(gameplay)
            except Exception:
                logger.exception('Could not recover coupon for completed gameplay %s', gameplay.pk)
        if gameplay.result in (Gameplay.Result.WON, Gameplay.Result.LOST):
            return render(request, 'games/already_played.html', {'gameplay': gameplay, 'coupon': coupon})
        table = gameplay.restaurant_table
        return render(request, 'games/game_play.html', {
            'game': gameplay.game,
            'gameplay': gameplay,
            'restaurant': gameplay.restaurant,
            'branch': table.branch if table else None,
            'table': table,
            'duration_seconds': int(gameplay.game.duration.total_seconds()),
            'game_ui': GAME_UI[gameplay.game.slug],
        })


class GameStartAPI(View):
    def post(self, request, slug):
        gameplay = _session_gameplay(request, slug)
        gameplay, started = start_gameplay(gameplay.pk, gameplay.customer_id)
        if not started:
            if (gameplay.result == Gameplay.Result.IN_PROGRESS and gameplay.deadline
                    and timezone.now() <= gameplay.deadline):
                return JsonResponse({
                    'ok': True, 'gameplay_id': gameplay.pk,
                    'duration': max(1, int((gameplay.deadline - timezone.now()).total_seconds())),
                    'deadline': gameplay.deadline.isoformat(), 'challenge': gameplay.challenge_data,
                    'resumed': True,
                })
            return JsonResponse({'ok': False, 'error': 'already_started'}, status=409)
        return JsonResponse({
            'ok': True,
            'gameplay_id': gameplay.pk,
            'duration': int(gameplay.game.duration.total_seconds()),
            'deadline': gameplay.deadline.isoformat(),
            'challenge': gameplay.challenge_data,
        })


class GameSubmitView(View):
    def post(self, request, slug):
        gameplay = _session_gameplay(request, slug)
        try:
            payload = json.loads(request.body)
        except (TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'invalid_payload'}, status=400)
        gameplay, accepted, reason = submit_gameplay(
            gameplay.pk,
            gameplay.customer_id,
            payload.get('outcome') == 'completed',
            payload.get('evidence') or {},
        )
        if not accepted:
            return JsonResponse({'ok': False, 'error': reason}, status=409)
        coupon_data = None
        coupon_error = None
        if gameplay.result == Gameplay.Result.WON:
            try:
                coupon = generate_coupon_for_gameplay(gameplay)
            except Exception:
                logger.exception('Could not generate coupon for gameplay %s', gameplay.pk)
                coupon = None
            if coupon:
                coupon_data = {
                    'code': coupon.coupon_code,
                    'reward': coupon.reward.title,
                    'valid_from': coupon.valid_from.isoformat() if coupon.valid_from else None,
                    'expiry_at': coupon.expiry_at.isoformat() if coupon.expiry_at else None,
                    'qr_url': coupon.qr_image.url if coupon.qr_image else None,
                    'view_url': None,
                }
                try:
                    coupon_data['view_url'] = public_coupon_url(request, coupon)
                except Exception:
                    logger.exception('Could not build coupon response for gameplay %s', gameplay.pk)
                    coupon_error = 'coupon_url_unavailable'
            else:
                coupon_error = (
                    'no_table_reward'
                    if not gameplay.restaurant_table_id or not gameplay.restaurant_table.reward_id
                    else 'no_active_reward'
                )
        return JsonResponse({
            'ok': True,
            'won': gameplay.result == Gameplay.Result.WON,
            'reason': reason,
            'stopped_at_seconds': (
                round(gameplay.play_time.total_seconds(), 1)
                if gameplay.game.slug == 'tap-at-ten' and gameplay.play_time else None
            ),
            'coupon': coupon_data,
            'coupon_error': coupon_error,
        })
