from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from ...models import Click, hash_ip


class RepeatClickFilterService:
    """Blocks an IP that was already sent on from the same link within TRAFFIC_FILTER_REPEAT_CLICK_HOURS."""

    reason = "repeat_click"

    def __init__(self, visit):
        self.visit = visit

    def matches(self):
        hours = settings.TRAFFIC_FILTER_REPEAT_CLICK_HOURS
        if not hours or not self.visit.ip:
            return False
        return Click.objects.filter(
            link=self.visit.link,
            ip_hash=hash_ip(self.visit.ip),
            blocked_reason="",
            created_at__gte=timezone.now() - timedelta(hours=hours),
        ).exists()
