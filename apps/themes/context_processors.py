from .runtime import get_active_theme_code


def theme(request):
    return {
        "THEME_CODE": get_active_theme_code(),
        "THEME_SETTINGS": getattr(request, "theme_settings", None),
    }
