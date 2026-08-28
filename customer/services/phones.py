import phonenumbers
from django.utils.translation import gettext as _


SUPPORTED_PHONE_COUNTRIES = {
    'IN': {'calling_code': '+91', 'label': _('India')},
    'AE': {'calling_code': '+971', 'label': _('United Arab Emirates')},
}


def normalize_phone_country(value):
    """Return a supported ISO country, preserving UAE when clearly specified."""
    normalized = (value or '').strip().upper()
    if normalized in {'AE', 'UAE', 'UNITED ARAB EMIRATES'}:
        return 'AE'
    return 'IN'


def normalize_phone(value, country='IN'):
    """Validate a national/explicit number and return canonical E.164 text."""
    country = normalize_phone_country(country)
    raw = (value or '').strip()
    if not raw:
        raise ValueError(_('Enter a valid phone number.'))
    try:
        number = phonenumbers.parse(raw, country)
    except phonenumbers.NumberParseException as exc:
        raise ValueError(_('Enter a valid phone number.')) from exc
    expected_code = phonenumbers.country_code_for_region(country)
    if number.country_code != expected_code or not phonenumbers.is_valid_number(number):
        raise ValueError(_('Enter a valid phone number.'))
    if phonenumbers.region_code_for_number(number) != country:
        raise ValueError(_('Enter a valid phone number.'))
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
