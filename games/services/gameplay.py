import random
import re
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from games.models import Game, Gameplay


ACTIVE_GAME_SLUGS = ('burger-stack', 'order-rush', 'memory-match', 'pizza-slice')
FOOD_ITEMS = ['☕', '🍔', '🍕', '🍟', '🥤', '🧁', '🍩', '🥪']
MEMORY_ITEMS = ['☕', '🍕', '🍔', '🍩', '🧁', '🍓']
GAME_UI = {
    'burger-stack': {'icon': '🍔', 'title': _('Build That Burger!'), 'description': _('Drop the ingredients at the right moment and build the perfect burger before time runs out!'), 'steps': [_('Watch the ingredient move.'), _('Tap anywhere to drop it.'), _('Stack all the ingredients.'), _('Finish before the timer reaches the flag!')], 'cta': _("Let's Stack! 🍔")},
    'order-rush': {'icon': '🧾', 'title': _('Remember the Order!'), 'description': _('A hungry customer is waiting! Memorize their order and recreate it before time runs out.'), 'steps': [_('Memorize the order.'), _('The order will disappear.'), _('Tap the items in the same order.'), _('Complete it before the flag!')], 'cta': _("I'm Ready! 👀")},
    'memory-match': {'icon': '🧠', 'title': _('Match the Treats!'), 'description': _('Find all the matching food pairs before time runs out!'), 'steps': [_('Tap a card to reveal it.'), _('Find its matching pair.'), _('Match every pair.'), _('Beat the timer!')], 'cta': _('Start Matching! ✨')},
    'pizza-slice': {'icon': '🍕', 'title': _('Perfect Slice!'), 'description': _('Time your taps and slice the pizza at just the right moment!'), 'steps': [_('Watch the moving cutter.'), _('Wait for the highlighted zone.'), _('Tap to make the cut.'), _('Complete three cuts in time!')], 'cta': _('Slice It! 🍕')},
}


def normalize_phone(value):
    value = (value or '').strip()
    prefix = '+' if value.startswith('+') else ''
    digits = re.sub(r'\D', '', value)
    if not 7 <= len(digits) <= 15:
        raise ValueError('Enter a valid phone or WhatsApp number.')
    return prefix + digits


def gameplay_today(customer, restaurant, day=None):
    day = day or timezone.localdate()
    return Gameplay.objects.filter(customer=customer, restaurant=restaurant, play_date=day).first()


@transaction.atomic
def assign_daily_game(customer, restaurant, table, request):
    existing = gameplay_today(customer, restaurant)
    if existing:
        return existing, False
    games = list(Game.objects.filter(slug__in=ACTIVE_GAME_SLUGS, is_active=True))
    if not games:
        raise Game.DoesNotExist('No PlayBite games are active.')
    game = random.SystemRandom().choice(games)
    try:
        gameplay = Gameplay.objects.create(
            customer=customer,
            restaurant=restaurant,
            restaurant_table=table,
            game=game,
            play_date=timezone.localdate(),
            ip_address=request.META.get('REMOTE_ADDR'),
            device=request.META.get('HTTP_USER_AGENT', '')[:255],
        )
    except IntegrityError:
        return gameplay_today(customer, restaurant), False
    return gameplay, True


def build_challenge(slug):
    rng = random.SystemRandom()
    if slug == 'burger-stack':
        return {'ingredients': ['lettuce', 'cheese', 'patty', 'tomato', 'top-bun'], 'max_mistakes': 2}
    if slug == 'order-rush':
        return {'order': rng.sample(FOOD_ITEMS, 4)}
    if slug == 'memory-match':
        deck = MEMORY_ITEMS * 2
        rng.shuffle(deck)
        return {'deck': deck, 'pairs': len(MEMORY_ITEMS)}
    if slug == 'pizza-slice':
        return {'zones': [{'center': rng.randrange(0, 360), 'width': 72} for _ in range(3)]}
    raise ValueError('Unsupported game.')


@transaction.atomic
def start_gameplay(gameplay_id, customer_id):
    gameplay = Gameplay.objects.select_for_update().select_related('game').get(
        pk=gameplay_id, customer_id=customer_id
    )
    if gameplay.result != Gameplay.Result.ASSIGNED or gameplay.started_at:
        return gameplay, False
    now = timezone.now()
    gameplay.started_at = now
    gameplay.deadline = now + gameplay.game.duration
    gameplay.result = Gameplay.Result.IN_PROGRESS
    gameplay.challenge_data = build_challenge(gameplay.game.slug)
    gameplay.save(update_fields=['started_at', 'deadline', 'result', 'challenge_data', 'updated_at'])
    return gameplay, True


def _angle_distance(a, b):
    return abs((float(a) - float(b) + 180) % 360 - 180)


def validate_objective(gameplay, evidence):
    try:
        evidence = evidence or {}
        if not isinstance(evidence, dict):
            return False
        challenge = gameplay.challenge_data
        slug = gameplay.game.slug
        if slug == 'burger-stack':
            placements = evidence.get('placements', [])
            return len(placements) == len(challenge.get('ingredients', [])) and all(
                0.45 <= float(overlap) <= 1 for overlap in placements
            )
        if slug == 'order-rush':
            return evidence.get('selection') == challenge.get('order')
        if slug == 'memory-match':
            deck = challenge.get('deck', [])
            pairs = evidence.get('pairs', [])
            used = set()
            for pair in pairs:
                if not isinstance(pair, list) or len(pair) != 2:
                    return False
                first, second = pair
                if first == second or first in used or second in used:
                    return False
                if not all(isinstance(index, int) and 0 <= index < len(deck) for index in pair):
                    return False
                if deck[first] != deck[second]:
                    return False
                used.update(pair)
            return len(used) == len(deck)
        if slug == 'pizza-slice':
            cuts = evidence.get('cuts', [])
            zones = challenge.get('zones', [])
            return len(cuts) == len(zones) and all(
                _angle_distance(cut, zone['center']) <= zone['width'] / 2 for cut, zone in zip(cuts, zones)
            )
    except (TypeError, ValueError, OverflowError):
        return False
    return False


@transaction.atomic
def submit_gameplay(gameplay_id, customer_id, claimed_complete, evidence):
    gameplay = Gameplay.objects.select_for_update().select_related('game', 'restaurant').get(
        pk=gameplay_id, customer_id=customer_id
    )
    if gameplay.submitted_at or gameplay.result in (Gameplay.Result.WON, Gameplay.Result.LOST):
        return gameplay, False, 'already_submitted'
    now = timezone.now()
    within_deadline = bool(gameplay.started_at and gameplay.deadline and now <= gameplay.deadline)
    won = bool(claimed_complete and within_deadline and validate_objective(gameplay, evidence))
    gameplay.result = Gameplay.Result.WON if won else Gameplay.Result.LOST
    gameplay.completed = won
    gameplay.score = 0
    gameplay.submitted_at = now
    gameplay.completed_at = now if won else None
    gameplay.play_time = now - gameplay.started_at if gameplay.started_at else None
    gameplay.save(update_fields=[
        'result', 'completed', 'score', 'submitted_at', 'completed_at', 'play_time', 'updated_at'
    ])
    return gameplay, True, None if won else ('deadline_expired' if not within_deadline else 'objective_incomplete')
