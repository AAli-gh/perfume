"""بازسازی ایندکس جستجوی همه محصولات (پس از تغییر ساختار سند جستجو، مثلاً افزودن مشخصات رایحه)."""

from django.core.management.base import BaseCommand

from apps.catalog.models import Product
from apps.catalog.search import reindex_products
from apps.catalog.smart_search import invalidate_vocab


class Command(BaseCommand):
    help = "بازسازی سند و بردار جستجوی همه محصولات"

    def handle(self, *args, **options):
        ids = list(Product.objects.values_list("pk", flat=True))
        for start in range(0, len(ids), 200):
            reindex_products(ids[start:start + 200])
        for store_id in set(Product.objects.values_list("store_id", flat=True)):
            invalidate_vocab(store_id)
        self.stdout.write(self.style.SUCCESS(f"ایندکس جستجوی {len(ids)} محصول بازسازی شد."))
