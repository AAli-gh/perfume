"""تست‌های معماری: جهت وابستگی بین ماژول‌ها را قفل می‌کنند تا با رشد پروژه، Coupling برنگردد."""

import ast
from pathlib import Path

import pytest

APPS_DIR = Path(__file__).resolve().parent.parent / "apps"

# هسته فروشگاه — نباید به لایه نمایش یا افزونه‌ها وابسته باشد
DOMAIN_APPS = ["accounts", "catalog", "cart", "orders", "blog"]
PRESENTATION_AND_EXTENSIONS = ["themes", "pages", "ai"]

# وابستگی‌های موقتی شناخته‌شده؛ هر مورد باید در Phase مشخص‌شده حذف شود.
KNOWN_EXCEPTIONS = {
    ("cart", "orders"): "Phase 2 — Coupon به اپ discounts منتقل می‌شود",
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


def test_cart_only_known_dependency_on_orders():
    deps = imported_apps("cart")
    unexpected = {d for d in deps if ("cart", d) not in KNOWN_EXCEPTIONS} - {"core", "catalog"}
    assert not unexpected, f"وابستگی غیرمجاز cart به: {unexpected}"


def test_no_dependency_cycle_between_orders_and_cart_views():
    """orders از cart استفاده می‌کند؛ cart.views نباید از orders چیزی import کند."""
    tree = ast.parse((APPS_DIR / "cart" / "views.py").read_text())
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not any(m.startswith("apps.orders") for m in modules)
