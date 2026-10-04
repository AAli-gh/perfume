from apps.core.models import StoreSettings


def site(request):
    store = getattr(request, "store", None)
    match = request.resolver_match
    site_context = {}
    if store is not None:
        try:
            site_context = store.config.as_site_context()
        except StoreSettings.DoesNotExist:
            site_context = {"name": store.name}
    return {
        "SITE": site_context,
        "STORE": store,
        "nav_section": match.namespace if match else "",
    }
