import hashlib
import io
import tarfile
import tempfile
from pathlib import Path
from unittest import mock

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import SimpleTestCase, TestCase, override_settings

from .models import Click, Link
from .services.download_geoip_database import DownloadGeoIPDatabaseService


class GoViewTests(TestCase):
    def setUp(self):
        self.link = Link.objects.create(code="3484x2z2w2a4u4q2r28463o5111")

    def test_redirects_and_counts_visit(self):
        response = self.client.get("/go/3484x2z2w2a4u4q2r28463o5111/", REMOTE_ADDR="203.0.113.7")

        self.assertEqual(response.status_code, 302)
        self.assertIn("juicy_code=3484x2z2w2a4u4q2r28463o5111", response["Location"])
        self.assertIn("no-cache", response["Cache-Control"])
        self.link.refresh_from_db()
        self.assertEqual(self.link.visits, 1)
        click = Click.objects.get()
        self.assertEqual(click.ip, "203.0.113.7")
        self.assertEqual(click.target_url, response["Location"])

    def test_unknown_code_is_404(self):
        self.assertEqual(self.client.get("/go/nope/").status_code, 404)
        self.assertFalse(Click.objects.exists())

    def test_forwarded_for_ignored_by_default(self):
        self.client.get(
            self.link.get_absolute_url(), REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="1.2.3.4"
        )
        self.assertEqual(Click.objects.get().ip, "10.0.0.1")

    @override_settings(USE_X_FORWARDED_FOR=True)
    def test_forwarded_for_used_when_enabled(self):
        self.client.get(
            self.link.get_absolute_url(),
            REMOTE_ADDR="172.18.0.2",
            HTTP_X_FORWARDED_FOR="1.2.3.4",
        )
        self.assertEqual(Click.objects.get().ip, "1.2.3.4")

    @override_settings(USE_X_FORWARDED_FOR=True)
    def test_spoofed_forwarded_for_entries_ignored(self):
        # Visitor sent "X-Forwarded-For: 6.6.6.6"; the proxy appended the real address.
        self.client.get(
            self.link.get_absolute_url(),
            REMOTE_ADDR="172.18.0.2",
            HTTP_X_FORWARDED_FOR="6.6.6.6, 1.2.3.4",
        )
        self.assertEqual(Click.objects.get().ip, "1.2.3.4")

    def test_code_validation(self):
        with self.assertRaises(ValidationError):
            Link(code="Bad Code!").full_clean()


class AdminTests(TestCase):
    def test_admin_requires_login(self):
        response = self.client.get("/admin/redirect/link/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    @override_settings(
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
    )
    def test_maxmind_attribution_in_footer(self):
        response = self.client.get("/admin/login/")
        self.assertContains(response, "GeoLite2 data created by MaxMind")
        self.assertContains(response, 'href="https://www.maxmind.com"')


def geoip_archive(content):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        info = tarfile.TarInfo("GeoLite2-City_20261003/GeoLite2-City.mmdb")
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


class DownloadGeoIPDatabaseTests(SimpleTestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(
            override_settings(
                MAXMIND_ACCOUNT_ID="123",
                MAXMIND_LICENSE_KEY="secret",
                MAXMIND_EDITION_ID="GeoLite2-City",
                MAXMIND_DATABASE_DIR=self.directory,
            )
        )
        self.urlopen = self.enterContext(
            mock.patch("src.redirect.services.download_geoip_database.service.urlopen")
        )

    def serve(self, archive, checksum=None):
        checksum = checksum or hashlib.sha256(archive).hexdigest()
        responses = {
            "tar.gz.sha256": f"{checksum}  GeoLite2-City_20261003.tar.gz\n".encode(),
            "tar.gz": archive,
        }
        self.urlopen.side_effect = lambda request, timeout: io.BytesIO(
            responses[request.full_url.rsplit("suffix=", 1)[1]]
        )

    def test_installs_database(self):
        self.serve(geoip_archive(b"mmdb-data"))

        self.assertTrue(DownloadGeoIPDatabaseService().execute())

        self.assertEqual((self.directory / "GeoLite2-City.mmdb").read_bytes(), b"mmdb-data")
        request = self.urlopen.call_args.args[0]
        self.assertEqual(request.unredirected_hdrs["Authorization"], "Basic MTIzOnNlY3JldA==")

    def test_skips_download_when_unchanged(self):
        self.serve(geoip_archive(b"mmdb-data"))
        DownloadGeoIPDatabaseService().execute()

        self.assertFalse(DownloadGeoIPDatabaseService().execute())
        self.assertEqual(self.urlopen.call_count, 3)  # checksum + archive, then checksum only

    def test_rejects_checksum_mismatch(self):
        self.serve(geoip_archive(b"mmdb-data"), checksum="0" * 64)

        with self.assertRaises(ValueError):
            DownloadGeoIPDatabaseService().execute()
        self.assertFalse((self.directory / "GeoLite2-City.mmdb").exists())

    @override_settings(MAXMIND_LICENSE_KEY="")
    def test_requires_credentials(self):
        with self.assertRaises(ImproperlyConfigured):
            DownloadGeoIPDatabaseService().execute()

