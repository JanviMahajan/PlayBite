import json
import datetime
from django.views import View
from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404
from django.utils import timezone

from .models import Game, Gameplay
from restaurants.models import RestaurantTable, Restaurant, Branch
from customer.models import Customer
from .services.validator import validate_gameplay


class GamePageView(View):
    def get(self, request, slug):
        # session must exist
        play_session = request.session.get('play_session')
        if not play_session or play_session.get('qr_slug') is None:
            return render(request, 'restaurants/play_invalid.html', status=404)

        # validate game exists and is active
        try:
            game = Game.objects.get(slug=slug, is_active=True)
        except Game.DoesNotExist:
            raise Http404('Game not found')

        # load restaurant/table context from session
        try:
            restaurant = Restaurant.objects.get(pk=play_session['restaurant_id'])
            branch = Branch.objects.get(pk=play_session['branch_id'])
            table = RestaurantTable.objects.get(pk=play_session['table_id'])
        except Exception:
            return render(request, 'restaurants/play_invalid.html', status=404)

        context = {
            'game': game,
            'restaurant': restaurant,
            'branch': branch,
            'table': table,
            'session_id': play_session.get('session_id'),
            'duration_seconds': int(game.duration.total_seconds()) if hasattr(game.duration, 'total_seconds') else 30,
        }
        return render(request, 'games/game_play.html', context)


class GameSubmitView(View):
    # POST endpoint to receive final score and validate
    def post(self, request, slug):
        play_session = request.session.get('play_session')
        if not play_session:
            return JsonResponse({'error': 'session_missing'}, status=400)

        try:
            payload = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'invalid_payload'}, status=400)

        score = int(payload.get('score', 0))
        time_taken = float(payload.get('time', 0))
        status = payload.get('status', 'completed')

        # validate game
        try:
            game = Game.objects.get(slug=slug)
        except Game.DoesNotExist:
            return JsonResponse({'error': 'invalid_game'}, status=404)

        # server-side validations using services
        max_time = int(game.duration.total_seconds()) if hasattr(game.duration, 'total_seconds') else 30
        ok, reason = validate_gameplay(slug, score, time_taken, max_time)
        if not ok:
            return JsonResponse({'error': reason}, status=400)

        # create or find a guest customer using session id
        session_id = play_session.get('session_id')
        phone_like = f'guest-{session_id}'
        customer, _ = Customer.objects.get_or_create(phone_number=phone_like, defaults={'full_name': 'Guest'})

        # create gameplay record
        try:
            restaurant = Restaurant.objects.get(pk=play_session['restaurant_id'])
            table = RestaurantTable.objects.get(pk=play_session['table_id'])
        except Exception:
            return JsonResponse({'error': 'invalid_session'}, status=400)

        gameplay = Gameplay.objects.create(
            customer=customer,
            restaurant=restaurant,
            restaurant_table=table,
            game=game,
            score=score,
            completed=(status == 'completed'),
            play_time=datetime.timedelta(seconds=int(time_taken)),
            ip_address=request.META.get('REMOTE_ADDR'),
            device=request.META.get('HTTP_USER_AGENT', '')[:255],
        )

        # determine eligibility and possibly generate coupon via rewards engine
        eligible = False
        coupon_data = None
        try:
            from coupons.services.generator import generate_coupon_for_gameplay
            coupon = generate_coupon_for_gameplay(gameplay)
            if coupon:
                eligible = True
                coupon_data = {
                    'coupon_id': coupon.pk,
                    'coupon_code': coupon.coupon_code,
                    'valid_from': coupon.valid_from.isoformat() if coupon.valid_from else None,
                    'expiry_at': coupon.expiry_at.isoformat() if coupon.expiry_at else None,
                }
        except Exception as e:
            # generator may fail; log in real app
            eligible = False

        return JsonResponse({'ok': True, 'gameplay_id': gameplay.pk, 'eligible': eligible, 'coupon': coupon_data})
