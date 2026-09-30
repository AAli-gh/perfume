from django.conf import settings


def site(request):
    match = request.resolver_match
    return {
        "SITE": settings.SITE_INFO,
        "nav_section": match.namespace if match else "",
    }
