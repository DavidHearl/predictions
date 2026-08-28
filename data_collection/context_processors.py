from django.conf import settings


def permissions(request):
    """Data pages are private: superusers only in production, everyone in local
    DEBUG runs (so development doesn't require logging in first)."""
    return {"can_view": request.user.is_superuser or settings.DEBUG}
