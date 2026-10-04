from django.conf import settings

_PROVIDERS = {}


def register(cls):
    _PROVIDERS[cls.code] = cls
    return cls


def provider_codes():
    return sorted(_PROVIDERS)


def get_provider():
    """ارائه‌دهنده پیکربندی‌شده یا None (پیامک خاموش)."""
    code = getattr(settings, "SMS_PROVIDER", "") or ""
    if not code:
        return None
    try:
        cls = _PROVIDERS[code]
    except KeyError as exc:
        raise LookupError(f"ارائه‌دهنده پیامک ناشناخته: {code} (موجود: {', '.join(provider_codes())})") from exc
    return cls(api_key=getattr(settings, "SMS_API_KEY", ""), sender=getattr(settings, "SMS_SENDER", ""))
