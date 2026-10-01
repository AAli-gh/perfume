"""ثبت و انتخاب ارائه‌دهنده AI بر اساس تنظیم AI_PROVIDER."""

from django.conf import settings

from .base import AIProvider, AIRequest, AIResponse, AIUnavailable, NullProvider

_REGISTRY: dict[str, type[AIProvider]] = {}


def register(provider_cls: type[AIProvider]) -> type[AIProvider]:
    _REGISTRY[provider_cls.code] = provider_cls
    return provider_cls


def get_provider() -> AIProvider:
    code = getattr(settings, "AI_PROVIDER", "") or ""
    if not code:
        return NullProvider()
    try:
        return _REGISTRY[code]()
    except KeyError as exc:
        raise AIUnavailable(f"ارائه‌دهنده AI ناشناخته: {code}") from exc


__all__ = ["AIProvider", "AIRequest", "AIResponse", "AIUnavailable", "NullProvider", "get_provider", "register"]
