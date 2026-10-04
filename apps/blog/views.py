from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from .models import Category, Post


def post_list(request):
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("cat", "")
    store = request.store
    published = Post.objects.for_store(store).published()
    posts = published.select_related("category")
    if cat:
        posts = posts.filter(category__slug=cat)
    if q:
        posts = posts.filter(Q(title__icontains=q) | Q(excerpt__icontains=q) | Q(body__icontains=q))
    page = Paginator(posts, 6).get_page(request.GET.get("page"))
    context = {
        "page": page,
        "q": q,
        "cat": cat,
        "categories": Category.objects.for_store(store)
        .annotate(n=Count("posts", filter=Q(posts__in=published)))
        .order_by(*Category._meta.ordering),  # GROUP BY ترتیب پیش‌فرض را حذف می‌کند
        "total": published.count(),
    }
    if request.htmx and not request.htmx.boosted:
        return render(request, "blog/partials/posts.html", context)
    return render(request, "blog/list.html", context)


def post_detail(request, slug):
    published = Post.objects.for_store(request.store).published()
    post = get_object_or_404(published.select_related("category"), slug=slug)
    more = published.exclude(pk=post.pk).select_related("category")[:2]
    return render(request, "blog/detail.html", {"post": post, "more": more})
