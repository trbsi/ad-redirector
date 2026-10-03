import ipaddress
from dataclasses import dataclass

from django.conf import settings
from django.db.models import F
from django.shortcuts import get_object_or_404

from ...models import Click, Link
from ..filtering import FILTERS, ChallengeService, Visit


@dataclass(frozen=True)
class RedirectResult:
    """Where to send the visitor, or a challenge token when the JavaScript check must run first."""

    url: str = ""
    challenge_token: str = ""


class RedirectService:
    """Filters a visit to a link and decides where it goes.

    Visits that pass every filter are counted, logged and sent to the link's target.
    Blocked visits are logged with the reason and sent to TRAFFIC_FILTER_BLOCKED_URL.
    """

    def __init__(self, request):
        self.request = request

    def execute(self, code):
        link = get_object_or_404(Link, code=code)
        ip = self.client_ip()
        reason = self.blocked_reason(Visit(self.request, link, ip))
        log_only = settings.TRAFFIC_FILTER_LOG_ONLY

        if reason and not log_only:
            blocked_url = settings.TRAFFIC_FILTER_BLOCKED_URL
            Click.objects.create(link=link, ip=ip, target_url=blocked_url, blocked_reason=reason)
            return RedirectResult(url=blocked_url)

        challenge = ChallengeService(self.request)
        if settings.TRAFFIC_FILTER_CHALLENGE and not log_only and not challenge.passed():
            return RedirectResult(challenge_token=challenge.token())

        target = link.target_url
        Link.objects.filter(pk=link.pk).update(visits=F("visits") + 1)
        # In log-only mode the reason is kept for review, but the visit goes through.
        Click.objects.create(link=link, ip=ip, target_url=target, blocked_reason=reason or "")
        return RedirectResult(url=target)

    def blocked_reason(self, visit):
        for filter_class in FILTERS:
            check = filter_class(visit)
            if check.matches():
                return check.reason
        return None

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
