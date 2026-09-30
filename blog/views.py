from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from .models import Category, Post


def post_list(request):
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("cat", "")
    posts = Post.objects.published().select_related("category")
    if cat:
        posts = posts.filter(category__slug=cat)
    if q:
        posts = posts.filter(Q(title__icontains=q) | Q(excerpt__icontains=q) | Q(body__icontains=q))
    page = Paginator(posts, 6).get_page(request.GET.get("page"))
    context = {
        "page": page,
        "q": q,
        "cat": cat,
        "categories": Category.objects.annotate(
            n=Count("posts", filter=Q(posts__in=Post.objects.published()))
        ),
        "total": Post.objects.published().count(),
    }
    if request.htmx and not request.htmx.boosted:
        return render(request, "blog/partials/posts.html", context)
    return render(request, "blog/list.html", context)


def post_detail(request, slug):
    post = get_object_or_404(Post.objects.published().select_related("category"), slug=slug)
    more = Post.objects.published().exclude(pk=post.pk).select_related("category")[:2]
    return render(request, "blog/detail.html", {"post": post, "more": more})
