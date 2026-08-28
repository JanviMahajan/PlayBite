import json
from datetime import timedelta
from urllib.parse import urlparse
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from coupons.models import Coupon, Redemption, Reward
from coupons.services.generator import generate_coupon_for_gameplay
from coupons.services.redeemer import redeem_coupon
from customer.models import Customer
from restaurants.models import Branch, Restaurant, RestaurantTable
from .models import Game, Gameplay
from .services.gameplay import ACTIVE_GAME_SLUGS, assign_daily_game, start_gameplay, submit_gameplay, validate_objective


class GameplayFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        owner = get_user_model().objects.create_user('game-owner@example.com', raw_password='x', full_name='Owner')
        cls.restaurant = Restaurant.objects.create(owner=owner, restaurant_name='Game Cafe')
        cls.branch = Branch.objects.create(restaurant=cls.restaurant, branch_name='Main', address='x', city='x', state='x', country='x')
        with patch.object(RestaurantTable, 'generate_qr_image'):
            cls.table = RestaurantTable.objects.create(branch=cls.branch, table_number='1')
            cls.table2 = RestaurantTable.objects.create(branch=cls.branch, table_number='2')
        cls.reward = Reward.objects.create(restaurant=cls.restaurant, title='Free Cookie', reward_type=Reward.RewardType.FREE_ITEM, coupon_valid_days=3)
        cls.reward.applicable_tables.add(cls.table, cls.table2)

    def setUp(self):
        self.table.refresh_from_db()
        self.table2.refresh_from_db()
        self.customer = Customer.objects.create(full_name='A', phone_number=f'+9100{Customer.objects.count():08d}')
        self.request = type('Request', (), {'META': {'REMOTE_ADDR':'127.0.0.1','HTTP_USER_AGENT':'test'}})()

    def assign(self, slug='order-rush'):
        Game.objects.filter(slug__in=ACTIVE_GAME_SLUGS).update(is_active=False)
        game = Game.objects.get(slug=slug); game.is_active=True; game.save(update_fields=['is_active'])
        gameplay, created = assign_daily_game(self.customer, self.restaurant, self.table, self.request)
        self.assertTrue(created)
        return gameplay

    @staticmethod
    def winning_evidence(gameplay):
        c=gameplay.challenge_data
        if gameplay.game.slug == 'burger-stack': return {'placements':[.8]*len(c['ingredients']),'mistakes':0}
        if gameplay.game.slug == 'order-rush': return {'selection':c['order'],'attempts':c['order']}
        if gameplay.game.slug == 'memory-match':
            grouped={}
            for i,item in enumerate(c['deck']): grouped.setdefault(item,[]).append(i)
            return {'pairs':list(grouped.values())}
        if gameplay.game.slug == 'pizza-slice': return {'cuts':[z['center'] for z in c['zones']]}
        return {'tap_ms':c['target_ms']}

    def start(self, gameplay):
        gameplay, started=start_gameplay(gameplay.pk,self.customer.pk);self.assertTrue(started);return gameplay

    def win_at_table(self, table, customer):
        Game.objects.filter(slug__in=ACTIVE_GAME_SLUGS).update(is_active=False)
        game=Game.objects.get(slug='order-rush');game.is_active=True;game.save(update_fields=['is_active'])
        gameplay,created=assign_daily_game(customer,self.restaurant,table,self.request)
        self.assertTrue(created)
        gameplay,started=start_gameplay(gameplay.pk,customer.pk);self.assertTrue(started)
        gameplay,accepted,reason=submit_gameplay(
            gameplay.pk,customer.pk,True,self.winning_evidence(gameplay),
        )
        self.assertTrue(accepted);self.assertIsNone(reason)
        return gameplay,generate_coupon_for_gameplay(gameplay)

    def test_each_objective_can_win_without_score(self):
        for index, slug in enumerate(ACTIVE_GAME_SLUGS):
            customer=Customer.objects.create(full_name=slug,phone_number=f'+919900000{index}')
            self.customer=customer
            gameplay=self.start(self.assign(slug))
            if slug == 'tap-at-ten':
                now=timezone.now();Gameplay.objects.filter(pk=gameplay.pk).update(started_at=now-timedelta(seconds=10),deadline=now+timedelta(seconds=5));gameplay.refresh_from_db()
            gameplay,accepted,reason=submit_gameplay(gameplay.pk,customer.pk,True,self.winning_evidence(gameplay))
            self.assertTrue(accepted);self.assertIsNone(reason);self.assertEqual(gameplay.result,Gameplay.Result.WON);self.assertEqual(gameplay.score,0)

    def test_loss_creates_no_coupon_and_counts_for_today(self):
        gameplay=self.start(self.assign()); gameplay,_,_=submit_gameplay(gameplay.pk,self.customer.pk,False,{})
        self.assertEqual(gameplay.result,Gameplay.Result.LOST)
        self.assertIsNone(generate_coupon_for_gameplay(gameplay))
        same,created=assign_daily_game(self.customer,self.restaurant,self.table2,self.request)
        self.assertFalse(created);self.assertEqual(same.pk,gameplay.pk)

    def test_win_creates_exactly_one_next_day_coupon(self):
        gameplay=self.start(self.assign()); gameplay,_,_=submit_gameplay(gameplay.pk,self.customer.pk,True,self.winning_evidence(gameplay))
        with patch.object(Coupon, 'generate_qr', return_value=None):
            first=generate_coupon_for_gameplay(gameplay);second=generate_coupon_for_gameplay(gameplay)
        self.assertEqual(first.pk,second.pk);self.assertEqual(Coupon.objects.count(),1)
        self.assertEqual(first.status,Coupon.Status.PENDING)
        self.assertEqual(timezone.localtime(first.valid_from).date(),timezone.localdate()+timedelta(days=1))
        self.assertEqual(timezone.localtime(first.expiry_at).date(), timezone.localdate()+timedelta(days=3))
        self.assertFalse(first.is_active_now())

    def test_each_table_win_uses_its_exact_assigned_reward(self):
        five=Reward.objects.create(restaurant=self.restaurant,title='5% Discount')
        ten=Reward.objects.create(restaurant=self.restaurant,title='10% Discount')
        self.reward.applicable_tables.clear()
        five.applicable_tables.add(self.table)
        ten.applicable_tables.add(self.table2)
        second=Customer.objects.create(full_name='B',phone_number='+919123450777')
        _,first_coupon=self.win_at_table(self.table,self.customer)
        _,second_coupon=self.win_at_table(self.table2,second)
        self.assertEqual(first_coupon.reward,five)
        self.assertEqual(second_coupon.reward,ten)

    def test_table_without_reward_creates_no_coupon_and_reports_friendly_reason(self):
        self.reward.applicable_tables.remove(self.table)
        gameplay=self.assign()
        session=self.client.session
        session['play_session']={'customer_id':self.customer.pk,'gameplay_id':gameplay.pk,'table_id':self.table.pk}
        session.save()
        self.client.post(reverse('games:game_start',args=[gameplay.game.slug]),data='{}',content_type='application/json')
        gameplay.refresh_from_db()
        response=self.client.post(
            reverse('games:game_submit',args=[gameplay.game.slug]),
            data=json.dumps({'outcome':'completed','evidence':self.winning_evidence(gameplay)}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['won'])
        self.assertEqual(response.json()['coupon_error'],'no_table_reward')
        self.assertFalse(Coupon.objects.filter(gameplay=gameplay).exists())

    def test_reward_configured_after_assignment_still_generates_coupon(self):
        self.reward.applicable_tables.remove(self.table)
        gameplay=self.start(self.assign())
        self.assertIsNone(gameplay.assigned_reward_id)
        self.reward.applicable_tables.add(self.table)
        gameplay,_,_=submit_gameplay(
            gameplay.pk,self.customer.pk,True,self.winning_evidence(gameplay),
        )
        coupon=generate_coupon_for_gameplay(gameplay)
        gameplay.refresh_from_db()
        self.assertIsNotNone(coupon)
        self.assertEqual(gameplay.assigned_reward,self.reward)
        self.assertEqual(coupon.reward,self.reward)

    def test_stale_ineligible_reward_is_replaced_from_same_table(self):
        tap_game=Game.objects.get(slug='tap-at-ten')
        stale=Reward.objects.create(
            restaurant=self.restaurant,title='Stale Coffee',is_active=True,
            game_eligibility=Reward.GameEligibility.SPECIFIC,
        )
        stale.eligible_games.add(tap_game)
        stale.applicable_tables.add(self.table)
        gameplay=self.start(self.assign('memory-match'))
        gameplay.assigned_reward=stale
        gameplay.save(update_fields=['assigned_reward','updated_at'])
        gameplay,_,_=submit_gameplay(
            gameplay.pk,self.customer.pk,True,self.winning_evidence(gameplay),
        )
        coupon=generate_coupon_for_gameplay(gameplay)
        gameplay.refresh_from_db()
        self.assertEqual(gameplay.assigned_reward,self.reward)
        self.assertEqual(coupon.reward,self.reward)

    def test_changing_table_reward_does_not_change_historical_coupon(self):
        original=Reward.objects.create(restaurant=self.restaurant,title='Original Table Reward')
        replacement=Reward.objects.create(restaurant=self.restaurant,title='Replacement Table Reward')
        self.reward.applicable_tables.remove(self.table)
        original.applicable_tables.add(self.table)
        _,coupon=self.win_at_table(self.table,self.customer)
        original.applicable_tables.remove(self.table)
        replacement.applicable_tables.add(self.table)
        coupon.refresh_from_db()
        self.assertEqual(coupon.reward,original)

    def test_shared_reward_assignments_remain_independent(self):
        shared=Reward.objects.create(restaurant=self.restaurant,title='Shared Reward')
        replacement=Reward.objects.create(restaurant=self.restaurant,title='Table One Reward')
        shared.applicable_tables.add(self.table, self.table2)
        shared.applicable_tables.remove(self.table)
        replacement.applicable_tables.add(self.table)
        self.assertEqual(list(replacement.applicable_tables.all()), [self.table])
        self.assertEqual(list(shared.applicable_tables.all()), [self.table2])

    def test_reward_dates_are_inclusive_and_coupon_window_starts_tomorrow(self):
        self.reward.start_date=timezone.localdate();self.reward.end_date=timezone.localdate();self.reward.coupon_valid_days=7;self.reward.save()
        gameplay=self.start(self.assign());gameplay,_,_=submit_gameplay(gameplay.pk,self.customer.pk,True,self.winning_evidence(gameplay))
        coupon=generate_coupon_for_gameplay(gameplay)
        self.assertIsNotNone(coupon)
        self.assertEqual(timezone.localtime(coupon.valid_from).date(),gameplay.play_date+timedelta(days=1))
        self.assertEqual(timezone.localtime(coupon.expiry_at).date(),gameplay.play_date+timedelta(days=7))

    def test_future_and_expired_rewards_are_not_eligible(self):
        gameplay=self.start(self.assign());gameplay,_,_=submit_gameplay(gameplay.pk,self.customer.pk,True,self.winning_evidence(gameplay))
        self.reward.start_date=gameplay.play_date+timedelta(days=1);self.reward.end_date=None;self.reward.save()
        self.assertIsNone(generate_coupon_for_gameplay(gameplay))
        self.reward.start_date=None;self.reward.end_date=gameplay.play_date-timedelta(days=1);self.reward.save()
        self.assertIsNone(generate_coupon_for_gameplay(gameplay))

    def test_reward_from_another_restaurant_is_never_used(self):
        gameplay=self.start(self.assign())
        owner=get_user_model().objects.create_user('reward-owner@example.com',raw_password='x',full_name='Reward Owner')
        other=Restaurant.objects.create(owner=owner,restaurant_name='Reward Cafe')
        wrong=Reward.objects.create(restaurant=other,title='Wrong Restaurant Reward',is_active=True)
        gameplay.assigned_reward=wrong;gameplay.save(update_fields=['assigned_reward','updated_at'])
        gameplay,_,_=submit_gameplay(gameplay.pk,self.customer.pk,True,self.winning_evidence(gameplay))
        self.assertIsNone(generate_coupon_for_gameplay(gameplay))

    def test_multiple_active_rewards_create_only_one_coupon(self):
        Reward.objects.create(restaurant=self.restaurant,title='New Reward',is_active=True)
        gameplay=self.start(self.assign());gameplay,_,_=submit_gameplay(gameplay.pk,self.customer.pk,True,self.winning_evidence(gameplay))
        coupon=generate_coupon_for_gameplay(gameplay)
        self.assertEqual(coupon.reward,self.reward)
        self.assertEqual(Coupon.objects.filter(gameplay=gameplay).count(),1)

    def test_coupon_lock_query_does_not_outer_join_nullable_relations(self):
        gameplay=self.start(self.assign());gameplay,_,_=submit_gameplay(gameplay.pk,self.customer.pk,True,self.winning_evidence(gameplay))
        with CaptureQueriesContext(connection) as queries:
            generate_coupon_for_gameplay(gameplay)
        gameplay_select=next(
            query['sql'] for query in queries.captured_queries
            if 'FROM "games_gameplay"' in query['sql']
        )
        self.assertNotIn('LEFT OUTER JOIN "restaurants_restauranttable"', gameplay_select)
        self.assertNotIn('LEFT OUTER JOIN "coupons_reward"', gameplay_select)

    def test_inactive_reward_blocks_coupon_until_activated(self):
        gameplay=self.start(self.assign());self.reward.is_active=False;self.reward.save(update_fields=['is_active'])
        gameplay,_,_=submit_gameplay(gameplay.pk,self.customer.pk,True,self.winning_evidence(gameplay))
        self.assertIsNone(generate_coupon_for_gameplay(gameplay))
        self.reward.is_active=True;self.reward.save(update_fields=['is_active'])
        self.assertIsNotNone(generate_coupon_for_gameplay(gameplay))

    def test_table_reward_redemption_limit_blocks_new_coupon(self):
        self.reward.max_total_redemptions=1
        self.reward.save(update_fields=['max_total_redemptions','updated_at'])
        redeemed=Coupon.objects.create(
            customer=self.customer,restaurant=self.restaurant,reward=self.reward,
            status=Coupon.Status.REDEEMED,
        )
        Redemption.objects.create(coupon=redeemed,redeemed_at=timezone.now())
        gameplay=self.start(self.assign())
        gameplay,_,_=submit_gameplay(
            gameplay.pk,self.customer.pk,True,self.winning_evidence(gameplay),
        )
        self.assertIsNone(generate_coupon_for_gameplay(gameplay))

    def test_coupon_token_does_not_depend_on_stored_qr_image(self):
        gameplay=self.start(self.assign());gameplay,_,_=submit_gameplay(gameplay.pk,self.customer.pk,True,self.winning_evidence(gameplay))
        coupon=generate_coupon_for_gameplay(gameplay)
        coupon.refresh_from_db()
        self.assertTrue(coupon.qr_token);self.assertFalse(coupon.qr_image)

    def test_refresh_recovers_single_coupon_for_saved_win(self):
        gameplay=self.start(self.assign());gameplay,_,_=submit_gameplay(gameplay.pk,self.customer.pk,True,self.winning_evidence(gameplay))
        session=self.client.session;session['play_session']={'customer_id':self.customer.pk,'gameplay_id':gameplay.pk};session.save()
        response=self.client.get(reverse('games:game_play',args=[gameplay.game.slug]))
        self.assertEqual(response.status_code,200);self.assertEqual(Coupon.objects.filter(gameplay=gameplay).count(),1)
        self.assertContains(response,'View Coupon')

    def test_coupon_activates_next_day_and_redeems_exactly_once(self):
        gameplay=self.start(self.assign());gameplay,_,_=submit_gameplay(gameplay.pk,self.customer.pk,True,self.winning_evidence(gameplay))
        coupon=generate_coupon_for_gameplay(gameplay)
        now=timezone.now();Coupon.objects.filter(pk=coupon.pk).update(status=Coupon.Status.ACTIVE,valid_from=now-timedelta(seconds=1),expiry_at=now+timedelta(days=1));coupon.refresh_from_db()
        first,redemption=redeem_coupon(self.restaurant.owner,qr_token=coupon.qr_token,branch=self.branch)
        second,reason=redeem_coupon(self.restaurant.owner,qr_token=coupon.qr_token,branch=self.branch)
        self.assertTrue(first);self.assertEqual(redemption.coupon_id,coupon.pk);self.assertFalse(second);self.assertEqual(reason,'already_redeemed')

    def test_bad_evidence_cannot_claim_a_win(self):
        gameplay=self.start(self.assign('pizza-slice'))
        invalid_cuts=[zone['center']+180 for zone in gameplay.challenge_data['zones']]
        gameplay,accepted,reason=submit_gameplay(gameplay.pk,self.customer.pk,True,{'cuts':invalid_cuts})
        self.assertTrue(accepted);self.assertEqual(reason,'objective_incomplete');self.assertEqual(gameplay.result,Gameplay.Result.LOST)

    def test_burger_uses_the_harder_server_overlap_threshold(self):
        gameplay=self.start(self.assign('burger-stack'))
        self.assertEqual(gameplay.challenge_data['min_overlap'],.68)
        self.assertFalse(validate_objective(gameplay,{'placements':[.8]*len(gameplay.challenge_data['ingredients']),'mistakes':1}))
        evidence={'placements':[.67]*len(gameplay.challenge_data['ingredients']),'mistakes':0}
        gameplay,accepted,reason=submit_gameplay(gameplay.pk,self.customer.pk,True,evidence)
        self.assertTrue(accepted);self.assertEqual(reason,'objective_incomplete');self.assertEqual(gameplay.result,Gameplay.Result.LOST)

    def test_order_rush_rejects_a_third_incorrect_tap(self):
        gameplay=self.start(self.assign('order-rush'))
        order=gameplay.challenge_data['order']
        wrong=next(item for item in ['☕','🍔','🍕','🍟','🥤','🧁','🍩','🥪'] if item != order[0])
        evidence={'selection':order,'attempts':[wrong,wrong,wrong,*order]}
        self.assertFalse(validate_objective(gameplay,evidence))

    def test_pizza_uses_narrower_zones_and_increasing_speed(self):
        gameplay=self.start(self.assign('pizza-slice'))
        self.assertTrue(all(zone['width']==68 for zone in gameplay.challenge_data['zones']))
        self.assertEqual(gameplay.challenge_data['base_speed'],135)
        self.assertEqual(gameplay.challenge_data['speed_step'],30)

    def test_duplicate_submission_is_rejected(self):
        gameplay=self.start(self.assign());evidence=self.winning_evidence(gameplay)
        submit_gameplay(gameplay.pk,self.customer.pk,True,evidence)
        _,accepted,reason=submit_gameplay(gameplay.pk,self.customer.pk,True,evidence)
        self.assertFalse(accepted);self.assertEqual(reason,'already_submitted')

    def test_server_deadline_overrides_browser_claim(self):
        gameplay=self.start(self.assign());Gameplay.objects.filter(pk=gameplay.pk).update(deadline=timezone.now()-timedelta(seconds=1));gameplay.refresh_from_db()
        gameplay,_,reason=submit_gameplay(gameplay.pk,self.customer.pk,True,self.winning_evidence(gameplay))
        self.assertEqual(reason,'deadline_expired');self.assertEqual(gameplay.result,Gameplay.Result.LOST)

    def test_database_daily_constraint_blocks_parallel_duplicate(self):
        gameplay=self.assign()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Gameplay.objects.create(customer=self.customer,restaurant=self.restaurant,restaurant_table=self.table2,game=gameplay.game,play_date=timezone.localdate())

    def test_same_customer_can_play_at_different_restaurant(self):
        owner=get_user_model().objects.create_user('other@example.com',raw_password='x',full_name='Other')
        other=Restaurant.objects.create(owner=owner,restaurant_name='Other Cafe')
        branch=Branch.objects.create(restaurant=other,branch_name='Main',address='x',city='x',state='x',country='x')
        with patch.object(RestaurantTable,'generate_qr_image'): table=RestaurantTable.objects.create(branch=branch,table_number='1')
        Reward.objects.create(restaurant=other,title='Other Treat',is_active=True)
        self.assign();_,created=assign_daily_game(self.customer,other,table,self.request);self.assertTrue(created)

    def test_tap_at_ten_rejects_browser_timing_without_matching_server_time(self):
        gameplay=self.start(self.assign('tap-at-ten'))
        gameplay,accepted,reason=submit_gameplay(
            gameplay.pk,self.customer.pk,True,{'tap_ms':10000},
        )
        self.assertTrue(accepted);self.assertEqual(reason,'objective_incomplete');self.assertEqual(gameplay.result,Gameplay.Result.LOST)

    def test_tap_result_reports_server_measured_stop_time(self):
        for index,seconds in enumerate((4,9)):
            self.customer=Customer.objects.create(
                full_name=f'Timer {seconds}',phone_number=f'+91955500000{index}',
            )
            gameplay=self.assign('tap-at-ten')
            session=self.client.session
            session['play_session']={'customer_id':self.customer.pk,'gameplay_id':gameplay.pk,'table_id':self.table.pk}
            session.save()
            self.client.post(
                reverse('games:game_start',args=['tap-at-ten']),data='{}',content_type='application/json',
            )
            now=timezone.now()
            Gameplay.objects.filter(pk=gameplay.pk).update(
                started_at=now-timedelta(seconds=seconds),deadline=now+timedelta(seconds=15-seconds),
            )
            response=self.client.post(
                reverse('games:game_submit',args=['tap-at-ten']),
                data=json.dumps({'outcome':'completed','evidence':{'tap_ms':seconds*1000}}),
                content_type='application/json',
            )
            self.assertFalse(response.json()['won'])
            self.assertAlmostEqual(response.json()['stopped_at_seconds'],seconds,delta=.2)

    def test_tap_at_ten_awards_game_specific_free_coffee(self):
        coffee=self.restaurant.rewards.get(title='Free Coffee')
        self.reward.applicable_tables.remove(self.table)
        coffee.applicable_tables.add(self.table)
        gameplay=self.start(self.assign('tap-at-ten'))
        now=timezone.now();Gameplay.objects.filter(pk=gameplay.pk).update(started_at=now-timedelta(seconds=10),deadline=now+timedelta(seconds=5));gameplay.refresh_from_db()
        gameplay,_,_=submit_gameplay(gameplay.pk,self.customer.pk,True,{'tap_ms':10000})
        coupon=generate_coupon_for_gameplay(gameplay)
        self.assertEqual(coupon.reward.title,'Free Coffee')
        self.assertTrue(coupon.reward.eligible_games.filter(slug='tap-at-ten').exists())

    def test_random_assignment_excludes_games_without_an_eligible_reward(self):
        self.restaurant.rewards.update(is_active=False)
        order_game=Game.objects.get(slug='order-rush')
        reward=Reward.objects.create(
            restaurant=self.restaurant,title='Order Treat',is_active=True,
            game_eligibility=Reward.GameEligibility.SPECIFIC,
        )
        reward.eligible_games.add(order_game)
        self.reward.applicable_tables.remove(self.table)
        reward.applicable_tables.add(self.table)
        Game.objects.filter(slug__in=ACTIVE_GAME_SLUGS).update(is_active=True)
        gameplay,created=assign_daily_game(self.customer,self.restaurant,self.table,self.request)
        self.assertTrue(created);self.assertEqual(gameplay.game.slug,'order-rush')

    def test_customer_is_eligible_on_next_date(self):
        old=self.assign();old.play_date=timezone.localdate()-timedelta(days=1);old.save(update_fields=['play_date'])
        _,created=assign_daily_game(self.customer,self.restaurant,self.table,self.request);self.assertTrue(created)

    def test_two_customers_each_receive_a_game(self):
        self.assign();second=Customer.objects.create(full_name='B',phone_number='+919123450001')
        _,created=assign_daily_game(second,self.restaurant,self.table,self.request);self.assertTrue(created)

    def test_http_flow_intro_start_win_coupon_and_refresh_lock(self):
        gameplay=self.assign();session=self.client.session;session['play_session']={'customer_id':self.customer.pk,'gameplay_id':gameplay.pk,'table_id':self.table.pk};session.save()
        page=self.client.get(reverse('games:game_play',args=[gameplay.game.slug]));self.assertContains(page,'How to Play');self.assertNotContains(page,'Score')
        started=self.client.post(reverse('games:game_start',args=[gameplay.game.slug]),data='{}',content_type='application/json');self.assertEqual(started.status_code,200)
        gameplay.refresh_from_db();payload={'outcome':'completed','evidence':self.winning_evidence(gameplay)}
        result=self.client.post(reverse('games:game_submit',args=[gameplay.game.slug]),data=json.dumps(payload),content_type='application/json')
        self.assertEqual(result.status_code,200);self.assertTrue(result.json()['won']);self.assertEqual(Coupon.objects.count(),1)
        coupon=Coupon.objects.get()
        self.assertEqual(result.json()['coupon']['id'],coupon.pk)
        self.assertEqual(result.json()['coupon']['reward_id'],coupon.reward_id)
        self.assertEqual(result.json()['coupon']['reward'],coupon.reward.title)
        self.assertIn('/coupon/view/', result.json()['coupon']['view_url'])
        duplicate=self.client.post(reverse('games:game_submit',args=[gameplay.game.slug]),data=json.dumps(payload),content_type='application/json');self.assertEqual(duplicate.status_code,409)
        refreshed=self.client.get(reverse('games:game_play',args=[gameplay.game.slug]));self.assertContains(refreshed,'That’s all for today!')

    def test_hidden_incomplete_coupon_is_reused_repaired_and_displayed(self):
        gameplay=self.assign()
        hidden=Coupon.objects.create(
            customer=self.customer,restaurant=self.restaurant,branch=self.branch,
            table=self.table,reward=self.reward,gameplay=gameplay,
            status=Coupon.Status.PENDING,qr_token=None,valid_from=None,expiry_at=None,
        )
        session=self.client.session
        session['play_session']={'customer_id':self.customer.pk,'gameplay_id':gameplay.pk,'table_id':self.table.pk}
        session.save()
        self.client.post(
            reverse('games:game_start',args=[gameplay.game.slug]),data='{}',content_type='application/json',
        )
        gameplay.refresh_from_db()
        response=self.client.post(
            reverse('games:game_submit',args=[gameplay.game.slug]),
            data=json.dumps({'outcome':'completed','evidence':self.winning_evidence(gameplay)}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['won'])
        self.assertEqual(Coupon.objects.filter(gameplay=gameplay).count(),1)
        hidden.refresh_from_db()
        self.assertTrue(hidden.qr_token)
        self.assertEqual(
            timezone.localtime(hidden.valid_from).date(),gameplay.play_date+timedelta(days=1),
        )
        view_url=response.json()['coupon']['view_url']
        self.assertTrue(view_url)
        coupon_page=self.client.get(urlparse(view_url).path)
        self.assertEqual(coupon_page.status_code,200)
        self.assertContains(coupon_page,self.reward.title)

    @patch('games.views.public_coupon_url', side_effect=RuntimeError('URL build failed'))
    def test_coupon_response_error_is_not_reported_as_missing_reward(self, _mock_url):
        gameplay=self.assign();session=self.client.session;session['play_session']={'customer_id':self.customer.pk,'gameplay_id':gameplay.pk,'table_id':self.table.pk};session.save()
        self.client.post(reverse('games:game_start',args=[gameplay.game.slug]),data='{}',content_type='application/json')
        gameplay.refresh_from_db();payload={'outcome':'completed','evidence':self.winning_evidence(gameplay)}
        response=self.client.post(reverse('games:game_submit',args=[gameplay.game.slug]),data=json.dumps(payload),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertIsNotNone(response.json()['coupon'])
        self.assertEqual(response.json()['coupon_error'],'coupon_url_unavailable')

    @patch('games.views.generate_coupon_for_gameplay', side_effect=RuntimeError('database failed'))
    def test_coupon_exception_is_not_masked_as_inactive_reward(self, _mock_generate):
        gameplay=self.assign()
        session=self.client.session
        session['play_session']={'customer_id':self.customer.pk,'gameplay_id':gameplay.pk,'table_id':self.table.pk}
        session.save()
        self.client.post(
            reverse('games:game_start',args=[gameplay.game.slug]),data='{}',content_type='application/json',
        )
        gameplay.refresh_from_db()
        response=self.client.post(
            reverse('games:game_submit',args=[gameplay.game.slug]),
            data=json.dumps({'outcome':'completed','evidence':self.winning_evidence(gameplay)}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['won'])
        self.assertIsNone(response.json()['coupon'])
        self.assertEqual(response.json()['coupon_error'],'coupon_generation_failed')

    def test_committed_coupon_is_returned_if_generator_raises_after_creation(self):
        gameplay=self.assign()
        session=self.client.session
        session['play_session']={'customer_id':self.customer.pk,'gameplay_id':gameplay.pk,'table_id':self.table.pk}
        session.save()
        self.client.post(
            reverse('games:game_start',args=[gameplay.game.slug]),data='{}',content_type='application/json',
        )
        gameplay.refresh_from_db()

        def create_then_raise(current_gameplay):
            generate_coupon_for_gameplay(current_gameplay)
            raise RuntimeError('post-creation operation failed')

        with patch('games.views.generate_coupon_for_gameplay', side_effect=create_then_raise):
            response=self.client.post(
                reverse('games:game_submit',args=[gameplay.game.slug]),
                data=json.dumps({'outcome':'completed','evidence':self.winning_evidence(gameplay)}),
                content_type='application/json',
            )
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['won'])
        self.assertIsNotNone(response.json()['coupon'])
        coupon=Coupon.objects.get(gameplay=gameplay)
        self.assertEqual(response.json()['coupon']['code'],coupon.coupon_code)
        self.assertEqual(response.json()['coupon']['reward'],coupon.reward.title)
        self.assertTrue(response.json()['coupon']['view_url'])
        self.assertEqual(Coupon.objects.filter(gameplay=gameplay).count(),1)
        self.assertEqual(self.client.get(urlparse(response.json()['coupon']['view_url']).path).status_code,200)
