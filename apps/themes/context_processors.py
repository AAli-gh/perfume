from django.utils.functional import SimpleLazyObject

from . import chrome
from .runtime import get_active_theme_code


def _header(request):
    header = chrome.resolve("header", getattr(request, "theme_settings", None))
    header["menu"] = [{**item, "active": chrome.is_active_link(item["url"], request.path)} for item in header["menu"]]
    return header


def theme(request):
    return {
        "THEME_CODE": get_active_theme_code(),
        "THEME_SETTINGS": getattr(request, "theme_settings", None),
        "THEME_HEADER": SimpleLazyObject(lambda: _header(request)),
        "THEME_FOOTER": SimpleLazyObject(lambda: chrome.resolve("footer", getattr(request, "theme_settings", None))),
    }
