from django.conf import settings
from django.core.management.base import BaseCommand

from ...services.download_tor_exit_nodes import DownloadTorExitNodesService


class Command(BaseCommand):
    help = "Download the current list of Tor exit node IPs."

    def handle(self, *args, **options):
        count = DownloadTorExitNodesService().execute()
        self.stdout.write(self.style.SUCCESS(f"Saved {count} addresses to {settings.TOR_EXIT_NODES_PATH}"))
