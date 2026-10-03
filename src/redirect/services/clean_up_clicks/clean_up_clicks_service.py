from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from ...models import Click


class CleanUpClicksService:
    """Applies the retention periods: clears old IPs and deletes old clicks (GDPR storage limitation).

    A period of 0 turns that step off. Link visit counts are stored on Link, so deleting clicks
    doesn't change them.
    """

    def execute(self):
        """Return how many clicks were deleted and anonymized, by step."""
        # Delete first, so IPs aren't cleared on rows that are about to be removed anyway.
        blocked_deleted = self.delete(
            Click.objects.exclude(blocked_reason=""), settings.BLOCKED_CLICK_RETENTION_DAYS
        )
        allowed_deleted = self.delete(
            Click.objects.filter(blocked_reason=""), settings.CLICK_RETENTION_DAYS
        )
        return {
            "ips_cleared": self.clear_ips(),
            "blocked_deleted": blocked_deleted,
            "allowed_deleted": allowed_deleted,
        }

    def clear_ips(self):
        days = settings.CLICK_IP_RETENTION_DAYS
        if not days:
            return 0
        return Click.objects.filter(created_at__lt=self.cutoff(days)).exclude(ip=None).update(ip=None)

    def delete(self, clicks, days):
        if not days:
            return 0
        deleted, _ = clicks.filter(created_at__lt=self.cutoff(days)).delete()
        return deleted

    @staticmethod
    def cutoff(days):
        return timezone.now() - timedelta(days=days)
