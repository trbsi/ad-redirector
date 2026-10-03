import ipaddress

from django.conf import settings
from django.db.models import F
from django.shortcuts import get_object_or_404

from ...models import Click, Link


class GoService:
    """Records a visit to a link and returns the URL to redirect to."""

    def __init__(self, request):
        self.request = request

    def execute(self, code):
        link = get_object_or_404(Link, code=code)
        target = link.target_url
        Link.objects.filter(pk=link.pk).update(visits=F("visits") + 1)
        Click.objects.create(link=link, ip=self.client_ip(), target_url=target)
        return target

    def client_ip(self):
        ip = self.request.META.get("REMOTE_ADDR")
        if settings.USE_X_FORWARDED_FOR:
            # Our proxy appends the address it saw to whatever the visitor sent,
            # so only the last entry can be trusted.
            forwarded = self.request.META.get("HTTP_X_FORWARDED_FOR", "")
            ip = forwarded.split(",")[-1].strip() or ip
        try:
            return str(ipaddress.ip_address(ip))
        except (TypeError, ValueError):
            return None
