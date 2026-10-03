import base64
import hashlib
import os
import shutil
import tarfile
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

DOWNLOAD_URL = "https://download.maxmind.com/geoip/databases/{edition}/download?suffix={suffix}"


class DownloadGeoIPDatabaseService:
    """Installs the latest MaxMind GeoLite2 database if it has changed since the last run."""

    def __init__(self):
        self.edition = settings.MAXMIND_EDITION_ID
        self.directory = Path(settings.MAXMIND_DATABASE_DIR)
        self.database_path = self.directory / f"{self.edition}.mmdb"
        self.checksum_path = self.directory / f"{self.edition}.tar.gz.sha256"

    def execute(self):
        """Return True if a new database was installed, False if it was already current."""
        if not (settings.MAXMIND_ACCOUNT_ID and settings.MAXMIND_LICENSE_KEY):
            raise ImproperlyConfigured("MAXMIND_ACCOUNT_ID and MAXMIND_LICENSE_KEY must be set")

        with self.fetch("tar.gz.sha256") as response:
            checksum = response.read().decode().split()[0]
        if self.database_path.exists() and self.installed_checksum() == checksum:
            return False

        self.directory.mkdir(parents=True, exist_ok=True)
        # Work inside the target directory so the final rename is atomic.
        with tempfile.TemporaryDirectory(dir=self.directory) as tmp:
            archive = Path(tmp) / "database.tar.gz"
            with self.fetch("tar.gz") as response, archive.open("wb") as out:
                shutil.copyfileobj(response, out)
            if self.sha256(archive) != checksum:
                raise ValueError(f"Checksum mismatch for downloaded {self.edition} archive")

            database = Path(tmp) / self.database_path.name
            self.extract(archive, database)
            os.replace(database, self.database_path)

        self.checksum_path.write_text(checksum + "\n")
        return True

    def fetch(self, suffix):
        request = Request(DOWNLOAD_URL.format(edition=self.edition, suffix=suffix))
        credentials = f"{settings.MAXMIND_ACCOUNT_ID}:{settings.MAXMIND_LICENSE_KEY}"
        # Unredirected, so the credentials aren't sent on to the storage host MaxMind redirects to.
        request.add_unredirected_header(
            "Authorization", "Basic " + base64.b64encode(credentials.encode()).decode()
        )
        return urlopen(request, timeout=120)

    def installed_checksum(self):
        try:
            return self.checksum_path.read_text().strip()
        except FileNotFoundError:
            return None

    def extract(self, archive, destination):
        name = self.database_path.name
        with tarfile.open(archive) as tar:
            member = next(
                (m for m in tar.getmembers() if m.isfile() and Path(m.name).name == name), None
            )
            if member is None:
                raise ValueError(f"{name} not found in downloaded archive")
            with tar.extractfile(member) as src, destination.open("wb") as out:
                shutil.copyfileobj(src, out)

    @staticmethod
    def sha256(path):
        digest = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
