from django.core.management.base import BaseCommand

from ...services.clean_up_clicks import CleanUpClicksService


class Command(BaseCommand):
    help = "Clear old visitor IPs and delete old clicks according to the retention settings."

    def handle(self, *args, **options):
        result = CleanUpClicksService().execute()
        self.stdout.write(
            self.style.SUCCESS(
                f"Cleared {result['ips_cleared']} IPs, deleted {result['blocked_deleted']} blocked "
                f"and {result['allowed_deleted']} allowed clicks"
            )
        )
