from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from ...services.download_geoip_database import DownloadGeoIPDatabaseService


class Command(BaseCommand):
    help = "Download the MaxMind databases in MAXMIND_EDITION_IDS that have a newer release."

    def handle(self, *args, **options):
        for edition in settings.MAXMIND_EDITION_IDS:
            service = DownloadGeoIPDatabaseService(edition)
            try:
                installed = service.execute()
            except ImproperlyConfigured as e:
                raise CommandError(e)
            if installed:
                self.stdout.write(self.style.SUCCESS(f"Installed {service.database_path}"))
            else:
                self.stdout.write(f"Already up to date: {service.database_path}")
