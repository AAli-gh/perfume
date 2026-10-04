"""sitemap.xml به تفکیک فروشگاه (فروشگاه جاری از StoreMiddleware) روی دامنه اصلی همان فروشگاه."""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.blog.models import Post
from apps.catalog.models import Category, Collection, Product
from apps.core.stores import get_current_store


class StoreSitemap(Sitemap):
    protocol = None  # همان پروتکل درخواست

    @property
    def store(self):
        return get_current_store()

    def get_domain(self, site=None):
        primary = self.store.domains.filter(is_primary=True).values_list("domain", flat=True).first()
        return primary or super().get_domain(site)


class StaticSitemap(StoreSitemap):
    changefreq = "weekly"
    PAGES = [("pages:home", 1.0), ("catalog:shop", 0.9), ("catalog:collections", 0.7), ("blog:list", 0.6),
             ("pages:about", 0.4), ("pages:contact", 0.4)]

    def items(self):
        return self.PAGES

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]


class ProductSitemap(StoreSitemap):
    changefreq, priority = "weekly", 0.8

    def items(self):
        return Product.objects.for_store(self.store).active().filter(noindex=False).order_by("pk")

    def lastmod(self, obj):
        return obj.updated_at


class CollectionSitemap(StoreSitemap):
    changefreq, priority = "weekly", 0.7

    def items(self):
        return Collection.objects.for_store(self.store).filter(noindex=False).order_by("pk")


class CategorySitemap(StoreSitemap):
    changefreq, priority = "weekly", 0.6

    def items(self):
        return Category.objects.for_store(self.store).filter(is_active=True, noindex=False).order_by("pk")


class PostSitemap(StoreSitemap):
    changefreq, priority = "monthly", 0.6

    def items(self):
        return Post.objects.for_store(self.store).published().filter(noindex=False).order_by("pk")

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {
    "pages": StaticSitemap,
    "products": ProductSitemap,
    "collections": CollectionSitemap,
    "categories": CategorySitemap,
    "posts": PostSitemap,
}
