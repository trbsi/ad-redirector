from urllib.error import URLError

from celery import shared_task
from django.conf import settings

from .services.clean_up_clicks import CleanUpClicksService
from .services.download_geoip_database import DownloadGeoIPDatabaseService
from .services.download_tor_exit_nodes import DownloadTorExitNodesService


@shared_task(autoretry_for=(URLError, TimeoutError), retry_backoff=60, max_retries=3)
def download_geoip_database():
    return {
        edition: DownloadGeoIPDatabaseService(edition).execute()
        for edition in settings.MAXMIND_EDITION_IDS
    }


@shared_task(autoretry_for=(URLError, TimeoutError), retry_backoff=60, max_retries=3)
def download_tor_exit_nodes():
    return DownloadTorExitNodesService().execute()


@shared_task
def clean_up_clicks():
    return CleanUpClicksService().execute()
