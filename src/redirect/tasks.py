from urllib.error import URLError

from celery import shared_task

from .services.download_geoip_database import DownloadGeoIPDatabaseService


@shared_task(autoretry_for=(URLError, TimeoutError), retry_backoff=60, max_retries=3)
def download_geoip_database():
    return DownloadGeoIPDatabaseService().execute()
