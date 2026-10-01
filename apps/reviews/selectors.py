from .models import Review


def approved_reviews(product):
    return Review.objects.filter(product=product, is_approved=True)
