"""تست‌های معماری: جهت وابستگی بین ماژول‌ها را قفل می‌کنند تا با رشد پروژه، Coupling برنگردد."""

import ast
from pathlib import Path

import pytest

APPS_DIR = Path(__file__).resolve().parent.parent / "apps"

# هسته فروشگاه — نباید به لایه نمایش یا افزونه‌ها وابسته باشد
DOMAIN_APPS = ["accounts", "catalog", "reviews", "discounts", "shipping", "cart", "wishlist", "orders", "payments", "blog",
               "marketing"]
PRESENTATION_AND_EXTENSIONS = ["themes", "pages", "builder", "seo", "ai", "notifications", "discovery"]

# وابستگی‌های مجاز هر اپ هسته (به‌جز core که هسته مشترک است)
ALLOWED_DEPENDENCIES = {
    "accounts": set(),
    "catalog": set(),
    "reviews": {"catalog"},
    "discounts": set(),
    "shipping": set(),
    "cart": {"catalog", "discounts", "shipping"},
    "orders": {"accounts", "catalog", "cart", "discounts", "shipping"},  # ← payments ندارد (Dependency Inversion)
    "payments": {"orders"},
    "wishlist": {"catalog"},
    "blog": set(),
    "marketing": set(),
}


def imported_apps(app):
    """نام اپ‌هایی که کد غیرتستی و غیرmigration یک اپ import می‌کند."""
    found = set()
    for path in (APPS_DIR / app).rglob("*.py"):
        if "migrations" in path.parts or "tests" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            for name in names:
                parts = name.split(".")
                if len(parts) > 1 and parts[0] == "apps" and parts[1] != app:
                    found.add(parts[1])
    return found


@pytest.mark.parametrize("app", DOMAIN_APPS)
def test_domain_does_not_depend_on_presentation_or_ai(app):
    assert not imported_apps(app) & set(PRESENTATION_AND_EXTENSIONS)


@pytest.mark.parametrize("app", [p.name for p in APPS_DIR.iterdir() if (p / "__init__.py").exists()])
def test_views_do_not_import_other_apps_views(app):
    views = APPS_DIR / app / "views.py"
    if not views.exists():
        return
    tree = ast.parse(views.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("apps."):
            assert not node.module.endswith(".views"), f"{app}/views.py imports {node.module}"


@pytest.mark.parametrize("app", DOMAIN_APPS)
def test_domain_dependencies_are_allowed(app):
    unexpected = imported_apps(app) - ALLOWED_DEPENDENCIES[app] - {"core"}
    assert not unexpected, f"وابستگی غیرمجاز {app} به: {unexpected}"


def test_no_import_cycles_between_apps():
    apps = [p.name for p in APPS_DIR.iterdir() if (p / "__init__.py").exists()]
    graph = {a: imported_apps(a) for a in apps}
    graph["core"] -= {"catalog", "reviews", "discounts", "blog"}  # seed_demo: ابزار توسعه، نه وابستگی زمان اجرا

    def visit(node, path):
        for dep in graph.get(node, ()):
            assert dep not in path, f"چرخه وابستگی: {' → '.join(path + [dep])}"
            visit(dep, path + [dep])

    for a in apps:
        visit(a, [a])


def test_no_dependency_cycle_between_orders_and_cart_views():
    """orders از cart استفاده می‌کند؛ cart.views نباید از orders چیزی import کند."""
    tree = ast.parse((APPS_DIR / "cart" / "views.py").read_text())
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not any(m.startswith("apps.orders") for m in modules)


# قالب‌هایی که جزو فروشگاه نیستند و قابل override توسط پوسته‌ها نیستند: رابط استودیو و ویجت‌های فرم
NON_STOREFRONT_TEMPLATES = ("builder/templates/builder/", "core/templates/core/widgets/")


def test_storefront_templates_live_in_themes_not_apps():
    """لایه نمایش جدا از منطق: قالب‌های فروشگاه فقط در themes/ هستند."""
    stray = [
        rel for p in APPS_DIR.rglob("templates/**/*.html")
        if not (rel := p.relative_to(APPS_DIR).as_posix()).startswith(NON_STOREFRONT_TEMPLATES)
    ]
    assert not stray, f"قالب در اپ‌ها: {stray}"


def test_themes_do_not_override_studio_templates():
    """استودیو مستقل از پوسته است؛ پوسته خراب نباید ابزار ویرایش را از کار بیندازد."""
    from apps.themes.loaders import PROTECTED_PREFIXES

    themes_dir = APPS_DIR.parent / "themes"
    assert "builder/" in PROTECTED_PREFIXES
    assert not list(themes_dir.glob("*/templates/builder/**/*.html"))
