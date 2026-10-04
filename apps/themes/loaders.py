"""Template Loader آگاه از پوسته.

ترتیب جستجو برای هر نام قالب:
    themes/<پوسته فعال>/templates/  ←  themes/base/templates/  ←  (loaderهای بعدی: قالب‌های Admin و اپ‌ها)

پوسته‌ها فقط فایل‌هایی را نگه می‌دارند که با لایه base فرق دارند؛ بقیه از base خوانده می‌شود (بدون کپی کد).
"""

from django.template.loaders.cached import Loader as CachedLoader
from django.template.loaders.filesystem import Loader as FilesystemLoader

from .registry import BASE_THEME, theme_path
from .runtime import get_active_theme_code


def theme_template_dirs(code):
    dirs = []
    for candidate in (code, BASE_THEME):
        path = theme_path(candidate)
        if path is not None and (path / "templates").is_dir():
            dirs.append(path / "templates")
    return dirs


# قالب‌هایی که پوسته‌ها نمی‌توانند تغییر دهند (رابط استودیو مستقل از پوسته فروشگاه است)
PROTECTED_PREFIXES = ("builder/", "admin/")


class ThemeLoader(FilesystemLoader):
    def get_dirs(self):
        return theme_template_dirs(get_active_theme_code())

    def get_template_sources(self, template_name):
        if template_name.startswith(PROTECTED_PREFIXES):
            return
        yield from super().get_template_sources(template_name)


class ThemeCachedLoader(CachedLoader):
    """cache قالب‌ها به تفکیک پوسته؛ cache پیش‌فرض Django فقط بر اساس نام قالب است و بین پوسته‌ها نشت می‌کند."""

    def cache_key(self, template_name, skip=None):
        return f"{get_active_theme_code()}:{super().cache_key(template_name, skip)}"
