"""به‌روزرسانی خودکار ایندکس جستجو هنگام تغییر محصول یا داده‌های مرتبط."""

from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .models import Brand, Category, Collection, FragranceNote, Product, ProductNote, ProductVariant, ScentFamily, Tag
from .search import reindex_products
from .smart_search import invalidate_vocab


@receiver(post_save, sender=Product)
def _product_saved(sender, instance, raw=False, **kwargs):
    if not raw:
        reindex_products([instance.pk])


@receiver([post_save, post_delete], sender=ProductNote)
def _note_link_changed(sender, instance, raw=False, **kwargs):
    if not raw:
        reindex_products([instance.product_id])


def _m2m_changed(sender, instance, action, pk_set=None, reverse=False, **kwargs):
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    if isinstance(instance, Product):
        reindex_products([instance.pk])
    elif pk_set:
        reindex_products(pk_set)


for _through in (Product.categories.through, Product.tags.through, Product.attribute_values.through):
    m2m_changed.connect(_m2m_changed, sender=_through, dispatch_uid=f"search-{_through._meta.label}")


@receiver(post_save, sender=Brand)
@receiver(post_save, sender=ScentFamily)
@receiver(post_save, sender=Collection)
@receiver(post_save, sender=Category)
@receiver(post_save, sender=Tag)
@receiver(post_save, sender=FragranceNote)
def _taxonomy_renamed(sender, instance, created=False, raw=False, **kwargs):
    """تغییر نام برند/نت/… ← بازسازی ایندکس محصولات مرتبط در پس‌زمینه (Celery)."""
    if raw or created:
        return
    from .tasks import reindex_products_task

    if sender is FragranceNote:
        ids = list(Product.objects.filter(notes__note=instance).values_list("pk", flat=True).distinct())
    else:
        ids = list(instance.products.values_list("pk", flat=True))
    if ids:
        transaction.on_commit(lambda: reindex_products_task.delay(ids))


@receiver([post_save, post_delete], sender=Product)
@receiver([post_save, post_delete], sender=ProductVariant)
@receiver([post_save, post_delete], sender=Brand)
@receiver([post_save, post_delete], sender=ScentFamily)
@receiver([post_save, post_delete], sender=FragranceNote)
def _smart_vocab_changed(sender, instance, raw=False, **kwargs):
    """واژگان جستجوی هوشمند (نام‌ها، نت‌ها، بازه قیمت) کش می‌شود؛ با هر تغییر پاک شود."""
    store_id = instance.product.store_id if sender is ProductVariant else getattr(instance, "store_id", None)
    if store_id:
        transaction.on_commit(lambda: invalidate_vocab(store_id))
