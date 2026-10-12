from celery import shared_task

from .search import reindex_products


@shared_task
def reindex_products_task(product_ids):
    reindex_products(product_ids)


@shared_task
def reindex_store_task(store_id):
    from .models import Product

    reindex_products(Product.objects.filter(store_id=store_id).values_list("pk", flat=True))


@shared_task
def prune_search_log_task():
    from .search_log import prune

    return prune()
