"""داده‌های ساختاریافته schema.org (JSON-LD).

خروجی همیشه با json_dumps_safe سریال می‌شود تا متن مدیر یا کاربر (مثلاً نام محصول با </script>) نتواند
از تگ <script type="application/ld+json"> بیرون بزند.
"""

import json

from django.urls import reverse

_ESCAPES = {ord("<"): "\\u003C", ord(">"): "\\u003E", ord("&"): "\\u0026", 0x2028: "\\u2028", 0x2029: "\\u2029"}
CONTEXT = "https://schema.org"


def json_dumps_safe(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).translate(_ESCAPES)


def breadcrumbs(items, absolute):
    """items: [(نام، مسیر)] ← BreadcrumbList"""
    return {
        "@context": CONTEXT,
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": absolute(url)}
            for i, (name, url) in enumerate(items, start=1)
        ],
    }


def organization(site, *, url, logo=None, description=""):
    data = {"@context": CONTEXT, "@type": "OnlineStore", "name": site.get("name", ""), "url": url}
    if logo:
        data["logo"] = logo
    if description:
        data["description"] = description
    if site.get("phone_link"):
        data["telephone"] = site["phone_link"]
    if site.get("email"):
        data["email"] = site["email"]
    if site.get("address"):
        data["address"] = {"@type": "PostalAddress", "streetAddress": site["address"], "addressCountry": "IR"}
    same_as = [site.get(k) for k in ("instagram", "telegram", "whatsapp")]
    same_as = [u for u in same_as if u and u.startswith(("https://", "http://"))]
    if same_as:
        data["sameAs"] = same_as
    return data


def website(site, *, url, absolute):
    return {
        "@context": CONTEXT,
        "@type": "WebSite",
        "name": site.get("name", ""),
        "url": url,
        "inLanguage": "fa-IR",
        "potentialAction": {
            "@type": "SearchAction",
            "target": {"@type": "EntryPoint", "urlTemplate": absolute(reverse("catalog:shop")) + "?q={search_term_string}"},
            "query-input": "required name=search_term_string",
        },
    }


def product(obj, *, url, images, description, currency_code, currency_factor):
    data = {
        "@context": CONTEXT,
        "@type": "Product",
        "name": obj.name,
        "url": url,
        "image": images,
        "description": description,
        "sku": obj.slug,
        "brand": {"@type": "Brand", "name": obj.brand.name},
        "category": obj.scent.name if obj.scent_id else "باکس هدیه",
    }
    variants = list(obj.variants.all())
    if variants:
        prices = [v.price * currency_factor for v in variants]
        in_stock = any(v.stock > 0 for v in variants)
        availability = f"https://schema.org/{'InStock' if in_stock else 'OutOfStock'}"
        if len(variants) == 1:
            data["offers"] = {"@type": "Offer", "price": prices[0], "priceCurrency": currency_code,
                              "availability": availability, "url": url}
        else:
            data["offers"] = {"@type": "AggregateOffer", "lowPrice": min(prices), "highPrice": max(prices),
                              "offerCount": len(variants), "priceCurrency": currency_code,
                              "availability": availability, "url": url}
    count = getattr(obj, "review_count", 0) or 0
    rating = getattr(obj, "rating_avg", None)
    if count and rating:
        data["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": round(float(rating), 1),
                                   "reviewCount": count, "bestRating": 5, "worstRating": 1}
    return data


def article(post, *, url, image, description, site_name, logo=None):
    publisher = {"@type": "Organization", "name": site_name}
    if logo:
        publisher["logo"] = {"@type": "ImageObject", "url": logo}
    data = {
        "@context": CONTEXT,
        "@type": "BlogPosting",
        "headline": post.title[:110],
        "description": description,
        "datePublished": post.published_at.isoformat(),
        "dateModified": (post.updated_at or post.published_at).isoformat(),
        "author": {"@type": "Organization", "name": site_name},
        "publisher": publisher,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "inLanguage": "fa-IR",
    }
    if image:
        data["image"] = [image]
    if getattr(post, "category", None):
        data["articleSection"] = post.category.name
    return data
