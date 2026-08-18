from io import BytesIO

import qrcode
from PIL import Image, ImageDraw, ImageFont
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View

from .services.presentation import (
    coupon_customer_status,
    coupon_from_private_token,
    public_coupon_url,
    whatsapp_share_url,
)


def _qr_png(token, size=520):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=12, border=3)
    qr.add_data(token)
    qr.make(fit=True)
    image = qr.make_image(fill_color='#211b2d', back_color='white').convert('RGB')
    return image.resize((size, size), Image.Resampling.LANCZOS)


def _font(size, bold=False):
    names = ['DejaVuSans-Bold.ttf', 'Arial Bold.ttf'] if bold else ['DejaVuSans.ttf', 'Arial.ttf']
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _centered(draw, text, y, font, fill):
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((900 - (box[2] - box[0])) / 2, y), text, font=font, fill=fill)


class CouponView(View):
    def get(self, request, token):
        coupon = coupon_from_private_token(token)
        status_key, status_label = coupon_customer_status(coupon)
        return render(request, 'coupons/customer_coupon.html', {
            'coupon': coupon,
            'status_key': status_key,
            'status_label': status_label,
            'coupon_url': public_coupon_url(request, coupon),
            'whatsapp_url': whatsapp_share_url(request, coupon),
            'qr_url': reverse('coupon_public:qr', kwargs={'token': token}),
            'download_url': reverse('coupon_public:download', kwargs={'token': token}),
        })


class CouponQRView(View):
    def get(self, request, token):
        coupon_from_private_token(token)
        output = BytesIO()
        _qr_png(token).save(output, format='PNG', optimize=True)
        return HttpResponse(output.getvalue(), content_type='image/png')


class CouponDownloadView(View):
    def get(self, request, token):
        coupon = coupon_from_private_token(token)
        canvas = Image.new('RGB', (900, 1300), '#fffaf3')
        draw = ImageDraw.Draw(canvas)
        orange, dark, muted = '#f27338', '#35251e', '#75635a'

        logo_path = finders.find('images/playbite-logo.png')
        if logo_path:
            try:
                logo = Image.open(logo_path).convert('RGBA')
                logo.thumbnail((120, 120), Image.Resampling.LANCZOS)
                canvas.paste(logo, ((900 - logo.width) // 2, 52), logo)
            except (OSError, ValueError):
                pass

        _centered(draw, 'PLAYBITE', 180, _font(38, True), orange)
        _centered(draw, coupon.reward.title, 255, _font(58, True), dark)
        _centered(draw, coupon.restaurant.restaurant_name, 335, _font(32), muted)
        _centered(draw, coupon.coupon_code, 405, _font(42, True), orange)

        qr_image = _qr_png(token, 500)
        canvas.paste(qr_image, (200, 485))

        valid_from = timezone.localtime(coupon.valid_from).strftime('%d %b %Y') if coupon.valid_from else '—'
        expiry = timezone.localtime(coupon.expiry_at).strftime('%d %b %Y') if coupon.expiry_at else '—'
        _centered(draw, f'{_("Valid From")}: {valid_from}', 1030, _font(28), dark)
        _centered(draw, f'{_("Expires")}: {expiry}', 1080, _font(28), dark)
        _centered(draw, _('Keep this coupon for your next visit ✨'), 1170, _font(25), muted)

        output = BytesIO()
        canvas.save(output, format='PNG', optimize=True)
        response = HttpResponse(output.getvalue(), content_type='image/png')
        response['Content-Disposition'] = f'attachment; filename="playbite-{coupon.coupon_code}.png"'
        return response
