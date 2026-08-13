from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import TemplateView, DetailView
from django.views.generic.edit import FormView, CreateView, UpdateView, DeleteView
from django.views.generic.list import ListView
from django.contrib.auth.mixins import LoginRequiredMixin

import uuid

from accounts.views import OwnerRequiredMixin
from .models import Restaurant, Branch, RestaurantTable
from .forms import RestaurantProfileForm, BranchForm, TableForm


from django.core.paginator import Paginator


class DashboardView(LoginRequiredMixin, OwnerRequiredMixin, TemplateView):
    template_name = 'restaurants/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['restaurant'] = self.request.user.restaurant
        except Restaurant.DoesNotExist:
            context['restaurant'] = None

        # Placeholder statistics
        stats = {
            'total_tables': 42,
            'active_branches': 3,
            'total_rewards': 12,
            'games_played_today': 128,
            'coupons_generated': 34,
            'coupons_redeemed': 9,
            'returning_customers': 21,
            'qr_scans_today': 76,
        }
        context['stats'] = stats

        # Placeholder chart data (structured for easy replacement with real data)
        context['charts'] = {
            'daily_plays': {
                'labels': [f'{i}' for i in range(1, 13)],
                'data': [5, 12, 9, 14, 20, 24, 30, 22, 18, 16, 12, 8],
            },
            'weekly_qr': {
                'labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                'data': [12, 19, 8, 14, 20, 30, 22],
            },
            'coupon_redemption': {
                'labels': ['Redeemed', 'Outstanding'],
                'data': [9, 25],
            },
            'popular_games': {
                'labels': ['Spin & Win', 'Trivia', 'Memory Match', 'Puzzle'],
                'data': [45, 30, 15, 10],
            },
            'peak_hours': {
                'labels': ['08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00'],
                'data': [5, 12, 30, 22, 18, 40, 25],
            },
        }

        # Recent activity placeholder list
        activities = [
            {'time': '09:12', 'customer': 'Aisha K', 'game': 'Spin & Win', 'reward': '10% Off', 'status': 'Delivered'},
            {'time': '09:05', 'customer': 'Ravi P', 'game': 'Trivia', 'reward': 'Free Drink', 'status': 'Pending'},
            {'time': '08:50', 'customer': 'Maya S', 'game': 'Memory Match', 'reward': '5% Off', 'status': 'Delivered'},
            {'time': '08:32', 'customer': 'Noah L', 'game': 'Puzzle', 'reward': 'Free Appetizer', 'status': 'Redeemed'},
            {'time': '08:10', 'customer': 'Liam G', 'game': 'Spin & Win', 'reward': '10% Off', 'status': 'Pending'},
            {'time': '07:58', 'customer': 'Olivia R', 'game': 'Trivia', 'reward': 'Free Drink', 'status': 'Delivered'},
            {'time': '07:45', 'customer': 'Emma C', 'game': 'Puzzle', 'reward': '5% Off', 'status': 'Delivered'},
            {'time': '07:30', 'customer': 'Sophia V', 'game': 'Memory Match', 'reward': 'Free Dessert', 'status': 'Pending'},
            {'time': '07:20', 'customer': 'Mason B', 'game': 'Spin & Win', 'reward': '10% Off', 'status': 'Delivered'},
            {'time': '07:02', 'customer': 'Isabella T', 'game': 'Trivia', 'reward': 'Free Drink', 'status': 'Delivered'},
        ]

        paginator = Paginator(activities, 5)
        page = self.request.GET.get('page')
        context['activity_page'] = paginator.get_page(page)

        return context


class RestaurantProfileView(LoginRequiredMixin, OwnerRequiredMixin, TemplateView):
    template_name = 'restaurants/profile_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['restaurant'] = get_object_or_404(Restaurant, owner=self.request.user)
        return context


class RestaurantProfileEditView(LoginRequiredMixin, OwnerRequiredMixin, FormView):
    template_name = 'restaurants/profile_edit.html'
    form_class = RestaurantProfileForm
    success_url = reverse_lazy('restaurants:restaurant_profile')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = get_object_or_404(Restaurant, owner=self.request.user)
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, 'Restaurant profile updated successfully.')
        return super().form_valid(form)


class BranchListView(LoginRequiredMixin, OwnerRequiredMixin, ListView):
    model = Branch
    template_name = 'restaurants/branch_list.html'
    context_object_name = 'branches'
    paginate_by = 8

    def get_queryset(self):
        qs = Branch.objects.filter(restaurant__owner=self.request.user).order_by('branch_name')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(branch_name__icontains=q)
        return qs


class BranchCreateView(LoginRequiredMixin, OwnerRequiredMixin, CreateView):
    model = Branch
    form_class = BranchForm
    template_name = 'restaurants/branch_form.html'
    success_url = reverse_lazy('restaurants:branch_list')

    def form_valid(self, form):
        restaurant = get_object_or_404(Restaurant, owner=self.request.user)
        form.instance.restaurant = restaurant
        messages.success(self.request, 'Branch created successfully.')
        return super().form_valid(form)


class BranchUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Branch
    form_class = BranchForm
    template_name = 'restaurants/branch_form.html'
    success_url = reverse_lazy('restaurants:branch_list')

    def get_queryset(self):
        return Branch.objects.filter(restaurant__owner=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Branch updated successfully.')
        return super().form_valid(form)


class BranchDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = Branch
    template_name = 'restaurants/branch_confirm_delete.html'
    success_url = reverse_lazy('restaurants:branch_list')

    def get_queryset(self):
        return Branch.objects.filter(restaurant__owner=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Branch deleted.')
        return super().delete(request, *args, **kwargs)


class TableListView(LoginRequiredMixin, OwnerRequiredMixin, ListView):
    model = RestaurantTable
    template_name = 'restaurants/table_list.html'
    context_object_name = 'tables'
    paginate_by = 20

    def get_queryset(self):
        qs = RestaurantTable.objects.filter(branch__restaurant__owner=self.request.user).select_related('branch').order_by('branch', 'table_number')
        q = self.request.GET.get('q')
        branch = self.request.GET.get('branch')
        status = self.request.GET.get('status')
        if q:
            qs = qs.filter(table_number__icontains=q)
        if branch:
            qs = qs.filter(branch_id=branch)
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['branches'] = Branch.objects.filter(restaurant__owner=self.request.user)
        return ctx


class TableCreateView(LoginRequiredMixin, OwnerRequiredMixin, CreateView):
    model = RestaurantTable
    form_class = TableForm
    template_name = 'restaurants/table_form.html'
    success_url = reverse_lazy('restaurants:table_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # limit branches to owner's branches
        form.fields['branch'].queryset = Branch.objects.filter(restaurant__owner=self.request.user)
        return form

    def form_valid(self, form):
        messages.success(self.request, 'Table created successfully. QR Pending')
        return super().form_valid(form)


class TableUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = RestaurantTable
    form_class = TableForm
    template_name = 'restaurants/table_form.html'
    success_url = reverse_lazy('restaurants:table_list')

    def get_queryset(self):
        return RestaurantTable.objects.filter(branch__restaurant__owner=self.request.user)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['branch'].queryset = Branch.objects.filter(restaurant__owner=self.request.user)
        return form

    def form_valid(self, form):
        messages.success(self.request, 'Table updated successfully.')
        return super().form_valid(form)


class TableDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = RestaurantTable
    template_name = 'restaurants/table_confirm_delete.html'
    success_url = reverse_lazy('restaurants:table_list')

    def get_queryset(self):
        return RestaurantTable.objects.filter(branch__restaurant__owner=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Table deleted.')
        return super().delete(request, *args, **kwargs)


class TableToggleActiveView(LoginRequiredMixin, OwnerRequiredMixin, TemplateView):
    def post(self, request, pk):
        table = get_object_or_404(RestaurantTable, pk=pk, branch__restaurant__owner=request.user)
        table.is_active = not table.is_active
        table.save(update_fields=['is_active'])
        messages.success(request, 'Table status updated.')
        return redirect('restaurants:table_list')


# QR management views
class QRListView(LoginRequiredMixin, OwnerRequiredMixin, ListView):
    model = RestaurantTable
    template_name = 'restaurants/qr_list.html'
    context_object_name = 'tables'
    paginate_by = 12

    def get_queryset(self):
        return RestaurantTable.objects.filter(branch__restaurant__owner=self.request.user).select_related('branch', 'branch__restaurant')


class QRDetailView(LoginRequiredMixin, OwnerRequiredMixin, DetailView):
    model = RestaurantTable
    template_name = 'restaurants/qr_detail.html'

    def get_queryset(self):
        return RestaurantTable.objects.filter(branch__restaurant__owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.conf import settings
        public_base_url = getattr(settings, 'PUBLIC_BASE_URL', '')
        context['scan_url'] = (
            f"{public_base_url.rstrip('/')}{self.object.get_qr_url()}"
            if public_base_url else self.request.build_absolute_uri(self.object.get_qr_url())
        )
        return context


from django.http import FileResponse, Http404
from io import BytesIO
from django.views import View


class QRDownloadPNGView(LoginRequiredMixin, OwnerRequiredMixin, View):
    def get(self, request, pk):
        table = get_object_or_404(RestaurantTable, pk=pk, branch__restaurant__owner=request.user)
        # If image not present, generate
        if not table.qr_image:
            table.generate_qr_image(save=True)
        if not table.qr_image:
            raise Http404('QR not available')
        try:
            return FileResponse(table.qr_image.open('rb'), as_attachment=True, filename=f'{table.branch.branch_name}_table_{table.table_number}.png')
        except Exception:
            raise Http404('QR not available')


class QRDownloadPDFView(LoginRequiredMixin, OwnerRequiredMixin, View):
    def get(self, request, pk):
        table = get_object_or_404(RestaurantTable, pk=pk, branch__restaurant__owner=request.user)
        # Ensure QR image
        if not table.qr_image:
            table.generate_qr_image(save=True)
        # Build a printable A4 PDF
        try:
            from PIL import Image, ImageDraw, ImageFont
        except Exception:
            raise Http404('PDF generation libraries missing')

        try:
            qr_path = table.qr_image.path
            qr_img = Image.open(qr_path).convert('RGB')
        except Exception:
            raise Http404('QR image missing')

        # Create A4 canvas at 300 DPI
        a4_px = (2480, 3508)
        canvas = Image.new('RGB', a4_px, 'white')
        draw = ImageDraw.Draw(canvas)

        # Paste QR centered
        qr_size = 1200
        qr_img = qr_img.resize((qr_size, qr_size))
        x = (a4_px[0] - qr_size) // 2
        y = 400
        canvas.paste(qr_img, (x, y))

        # Add text
        try:
            font = ImageFont.truetype('arial.ttf', 48)
        except Exception:
            font = ImageFont.load_default()
        title = table.branch.restaurant.restaurant_name
        subtitle = f'Branch: {table.branch.branch_name} — Table {table.table_number}'
        w, h = draw.textsize(title, font=font)
        draw.text(((a4_px[0]-w)/2, 80), title, fill=(0,0,0), font=font)
        sw, sh = draw.textsize(subtitle, font=font)
        draw.text(((a4_px[0]-sw)/2, 150), subtitle, fill=(80,80,80), font=font)

        bio = BytesIO()
        canvas.save(bio, format='PDF', resolution=300)
        bio.seek(0)
        return FileResponse(bio, as_attachment=True, filename=f'{table.branch.branch_name}_table_{table.table_number}.pdf')


class QRRegenerateView(LoginRequiredMixin, OwnerRequiredMixin, View):
    def post(self, request, pk):
        table = get_object_or_404(RestaurantTable, pk=pk, branch__restaurant__owner=request.user)
        # generate new slug and image
        table.qr_slug = uuid.uuid4()
        table.save(update_fields=['qr_slug'])
        table.generate_qr_image(save=True)
        messages.success(request, 'QR regenerated successfully.')
        return redirect('restaurants:qr_list')


from django.views.decorators.http import require_GET
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie


from django.utils import timezone
from django.views import View
from django.http import JsonResponse


@method_decorator(ensure_csrf_cookie, name='dispatch')
class PlayWelcomeView(View):
    """Public customer-facing welcome/play entry. Validates QR and creates a temporary session."""
    def get(self, request, qr_slug):
        try:
            table = RestaurantTable.objects.select_related('branch__restaurant').get(qr_slug=qr_slug)
        except RestaurantTable.DoesNotExist:
            return render(request, 'restaurants/play_invalid.html', status=404)

        # Validate restaurant/branch/table active
        restaurant = table.branch.restaurant
        if not (restaurant.is_active and table.branch.is_active and table.is_active):
            return render(request, 'restaurants/play_invalid.html', status=404)

        # Create a temporary session entry
        session_id = str(uuid.uuid4())
        play_session = {
            'session_id': session_id,
            'qr_slug': str(qr_slug),
            'restaurant_id': restaurant.pk,
            'branch_id': table.branch.pk,
            'table_id': table.pk,
            'scanned_at': timezone.now().isoformat(),
        }
        # store minimal server-side session keyed by session_id
        request.session['play_session'] = play_session
        request.session.modified = True

        # Log scan
        try:
            ip = request.META.get('REMOTE_ADDR')
            ua = request.META.get('HTTP_USER_AGENT', '')
            from .models import QRScan
            QRScan.objects.create(table=table, ip_address=ip, user_agent=ua)
        except Exception:
            pass

        context = {
            'restaurant': restaurant,
            'branch': table.branch,
            'table': table,
            'session_id': session_id,
        }
        return render(request, 'restaurants/play_welcome.html', context)


class PlayOffersView(View):
    """Show active rewards for this restaurant."""
    def get(self, request, qr_slug):
        # validate session and qr
        try:
            table = RestaurantTable.objects.select_related('branch__restaurant').get(qr_slug=qr_slug)
        except RestaurantTable.DoesNotExist:
            return render(request, 'restaurants/play_invalid.html', status=404)

        restaurant = table.branch.restaurant
        if not (restaurant.is_active and table.branch.is_active and table.is_active):
            return render(request, 'restaurants/play_invalid.html', status=404)

        # fetch active rewards
        try:
            from coupons.models import Reward
            rewards = Reward.objects.filter(restaurant=restaurant, is_active=True)
        except Exception:
            rewards = []

        return render(request, 'restaurants/play_offers.html', {'rewards': rewards, 'restaurant': restaurant, 'qr_slug': qr_slug})


class PlayInstructionsView(View):
    def get(self, request, qr_slug):
        try:
            table = RestaurantTable.objects.select_related('branch__restaurant').get(qr_slug=qr_slug)
        except RestaurantTable.DoesNotExist:
            return render(request, 'restaurants/play_invalid.html', status=404)

        restaurant = table.branch.restaurant
        if not (restaurant.is_active and table.branch.is_active and table.is_active):
            return render(request, 'restaurants/play_invalid.html', status=404)

        return render(request, 'restaurants/play_instructions.html', {'restaurant': restaurant, 'qr_slug': qr_slug})


import random


class PlayStartView(View):
    """Lightweight identity, daily eligibility check, and server game assignment."""
    def _table(self, qr_slug):
        try:
            table = RestaurantTable.objects.select_related('branch__restaurant').get(qr_slug=qr_slug)
        except RestaurantTable.DoesNotExist:
            return None
        restaurant = table.branch.restaurant
        if not (restaurant.is_active and table.branch.is_active and table.is_active):
            return None
        return table

    def get(self, request, qr_slug):
        table = self._table(qr_slug)
        if not table:
            return render(request, 'restaurants/play_invalid.html', status=404)
        return render(request, 'games/identify.html', {'table': table, 'restaurant': table.branch.restaurant})

    def post(self, request, qr_slug):
        table = self._table(qr_slug)
        if not table:
            return render(request, 'restaurants/play_invalid.html', status=404)
        from customer.models import Customer
        from games.services.gameplay import assign_daily_game, normalize_phone
        try:
            phone = normalize_phone(request.POST.get('phone_number'))
        except ValueError as exc:
            return render(request, 'games/identify.html', {
                'table': table, 'restaurant': table.branch.restaurant, 'error': str(exc),
                'full_name': request.POST.get('full_name', ''),
            }, status=400)
        full_name = request.POST.get('full_name', '').strip()
        if not full_name:
            return render(request, 'games/identify.html', {
                'table': table, 'restaurant': table.branch.restaurant,
                'error': 'Please enter your name.', 'phone_number': phone,
            }, status=400)
        customer, created = Customer.objects.get_or_create(
            phone_number=phone,
            defaults={'full_name': full_name, 'whatsapp_number': phone},
        )
        if not created and customer.full_name != full_name:
            customer.full_name = full_name
            customer.save(update_fields=['full_name', 'updated_at'])
        gameplay, assigned = assign_daily_game(customer, table.branch.restaurant, table, request)
        play_session = request.session.get('play_session', {})
        play_session.update({'customer_id': customer.pk, 'gameplay_id': gameplay.pk})
        request.session['play_session'] = play_session
        if not assigned:
            coupon = gameplay.coupons.first()
            return render(request, 'games/already_played.html', {'gameplay': gameplay, 'coupon': coupon})
        return redirect('games:game_play', slug=gameplay.game.slug)


# Keep backward-compatible name for top-level import used in playbite.urls earlier
PlayView = PlayWelcomeView
