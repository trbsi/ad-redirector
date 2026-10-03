import hashlib
import io
import tarfile
import tempfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from geoip2.errors import AddressNotFoundError

from .models import Click, Link, hash_ip
from .services.clean_up_clicks import CleanUpClicksService
from .services.download_geoip_database import DownloadGeoIPDatabaseService
from .services.download_tor_exit_nodes import DownloadTorExitNodesService


BROWSER = {
    "HTTP_USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "HTTP_ACCEPT": "text/html,application/xhtml+xml",
    "HTTP_ACCEPT_LANGUAGE": "en-US,en;q=0.9",
}

FILTERS_OFF = dict(
    TRAFFIC_FILTER_LOG_ONLY=False,
    TRAFFIC_FILTER_BLOCKED_URL="/",
    TRAFFIC_FILTER_ALLOWED_COUNTRIES=frozenset(),
    TRAFFIC_FILTER_BLOCKED_COUNTRIES=frozenset(),
    TRAFFIC_FILTER_EXTRA_BLOCKED_ASNS=frozenset(),
    TRAFFIC_FILTER_REPEAT_CLICK_HOURS=0,
    TRAFFIC_FILTER_CHALLENGE=False,
    MAXMIND_DATABASE_DIR=Path("/nonexistent"),
    TOR_EXIT_NODES_PATH=Path("/nonexistent/tor-exit-nodes.txt"),
)


@override_settings(**FILTERS_OFF)
class GoViewTests(TestCase):
    def setUp(self):
        self.link = Link.objects.create(code="3484x2z2w2a4u4q2r28463o5111")
        self.client.defaults.update(BROWSER)

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
        self.assertEqual(click.blocked_reason, "")
        self.assertEqual(click.ip_hash, hash_ip("203.0.113.7"))

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


def geo(country=None, asn=None, org="", anonymous=False, missing=False):
    """A stand-in for a geoip2 reader."""

    def lookup(record):
        def method(ip):
            if missing:
                raise AddressNotFoundError(ip)
            return record

        return method

    return SimpleNamespace(
        country=lookup(SimpleNamespace(country=SimpleNamespace(iso_code=country))),
        asn=lookup(
            SimpleNamespace(autonomous_system_number=asn, autonomous_system_organization=org)
        ),
        anonymous_ip=lookup(SimpleNamespace(is_anonymous=anonymous)),
    )


@override_settings(**FILTERS_OFF)
class FilteringTests(TestCase):
    def setUp(self):
        self.link = Link.objects.create(code="abc123")
        self.client.defaults.update(BROWSER)

    def visit(self, **extra):
        return self.client.get("/go/abc123/", REMOTE_ADDR="203.0.113.7", **extra)

    def assertBlocked(self, response, reason):
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        click = Click.objects.get()
        self.assertEqual(click.blocked_reason, reason)
        self.link.refresh_from_db()
        self.assertEqual(self.link.visits, 0)

    def assertAllowed(self, response):
        self.assertEqual(response.status_code, 302)
        self.assertIn("juicy_code=abc123", response["Location"])

    def patch_reader(self, filter_name, database):
        self.enterContext(
            mock.patch(
                f"src.redirect.services.filtering.{filter_name}_filter_service.reader",
                return_value=database,
            )
        )

    def test_preview_crawler(self):
        response = self.visit(HTTP_USER_AGENT="facebookexternalhit/1.1")
        self.assertBlocked(response, "preview_crawler")

    def test_bot_user_agent(self):
        self.assertBlocked(self.visit(HTTP_USER_AGENT="python-requests/2.32"), "bot")

    def test_phone_model_containing_bot_allowed(self):
        user_agent = (
            "Mozilla/5.0 (Linux; Android 13; CUBOT X30) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36"
        )
        self.assertAllowed(self.visit(HTTP_USER_AGENT=user_agent))

    def test_bot_missing_browser_headers(self):
        self.assertBlocked(self.visit(HTTP_ACCEPT_LANGUAGE=""), "bot")

    @override_settings(TRAFFIC_FILTER_ALLOWED_COUNTRIES=frozenset({"US", "GB"}))
    def test_country_not_allowed(self):
        self.patch_reader("country", geo(country="DE"))
        self.assertBlocked(self.visit(), "country")

    @override_settings(TRAFFIC_FILTER_ALLOWED_COUNTRIES=frozenset({"US", "GB"}))
    def test_country_allowed(self):
        self.patch_reader("country", geo(country="US"))
        self.assertAllowed(self.visit())

    @override_settings(TRAFFIC_FILTER_ALLOWED_COUNTRIES=frozenset({"US"}))
    def test_unknown_country_blocked_when_allow_list_set(self):
        self.patch_reader("country", geo(missing=True))
        self.assertBlocked(self.visit(), "country")

    @override_settings(TRAFFIC_FILTER_BLOCKED_COUNTRIES=frozenset({"CN"}))
    def test_country_blocked(self):
        self.patch_reader("country", geo(country="CN"))
        self.assertBlocked(self.visit(), "country")

    @override_settings(TRAFFIC_FILTER_ALLOWED_COUNTRIES=frozenset({"US"}))
    def test_missing_database_lets_visits_through(self):
        self.assertAllowed(self.visit())

    def test_datacenter_asn(self):
        self.patch_reader("datacenter", geo(asn=16509, org="AMAZON-02"))
        self.assertBlocked(self.visit(), "datacenter")

    def test_datacenter_keyword(self):
        self.patch_reader("datacenter", geo(asn=64500, org="Example Hosting Ltd"))
        self.assertBlocked(self.visit(), "datacenter")

    @override_settings(TRAFFIC_FILTER_EXTRA_BLOCKED_ASNS=frozenset({64500}))
    def test_datacenter_extra_asn(self):
        self.patch_reader("datacenter", geo(asn=64500, org="Example ISP"))
        self.assertBlocked(self.visit(), "datacenter")

    def test_home_network_allowed(self):
        self.patch_reader("datacenter", geo(asn=7922, org="COMCAST-7922"))
        self.assertAllowed(self.visit())

    def test_anonymous_ip(self):
        self.patch_reader("anonymous_ip", geo(anonymous=True))
        self.assertBlocked(self.visit(), "anonymous_ip")

    def test_tor_exit_node(self):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (directory / "tor.txt").write_text("198.51.100.1\n203.0.113.7\n")
        with self.settings(TOR_EXIT_NODES_PATH=directory / "tor.txt"):
            self.assertBlocked(self.visit(), "tor")

    @override_settings(TRAFFIC_FILTER_REPEAT_CLICK_HOURS=24)
    def test_repeat_click(self):
        self.assertAllowed(self.visit())
        response = self.visit()

        self.assertEqual(response["Location"], "/")
        self.assertEqual(
            list(Click.objects.order_by("id").values_list("blocked_reason", flat=True)),
            ["", "repeat_click"],
        )

    @override_settings(TRAFFIC_FILTER_REPEAT_CLICK_HOURS=24)
    def test_repeat_click_after_ip_cleared(self):
        # The full IP is gone after CLICK_IP_RETENTION_DAYS; the hash still recognizes the visitor.
        self.assertAllowed(self.visit())
        Click.objects.update(ip=None)
        self.assertEqual(self.visit()["Location"], "/")

    @override_settings(TRAFFIC_FILTER_REPEAT_CLICK_HOURS=24)
    def test_repeat_click_after_window(self):
        Click.objects.create(
            link=self.link,
            ip="203.0.113.7",
            target_url="http://example.com",
            created_at=timezone.now() - timedelta(hours=25),
        )
        self.assertAllowed(self.visit())

    @override_settings(TRAFFIC_FILTER_BLOCKED_URL="https://example.com/sorry")
    def test_custom_blocked_url(self):
        response = self.visit(HTTP_USER_AGENT="curl/8.0")
        self.assertEqual(response["Location"], "https://example.com/sorry")

    @override_settings(TRAFFIC_FILTER_LOG_ONLY=True, TRAFFIC_FILTER_CHALLENGE=True)
    def test_log_only_records_reason_but_redirects(self):
        response = self.visit(HTTP_USER_AGENT="curl/8.0")

        self.assertAllowed(response)
        self.assertEqual(Click.objects.get().blocked_reason, "bot")
        self.link.refresh_from_db()
        self.assertEqual(self.link.visits, 1)

    @override_settings(TRAFFIC_FILTER_CHALLENGE=True)
    def test_challenge_then_redirect(self):
        response = self.visit()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "location.replace")
        self.assertContains(response, 'href="/privacy/"')
        self.assertFalse(Click.objects.exists())

        token = response.context["token"]
        self.client.cookies["rc"] = token
        self.assertAllowed(self.visit())
        self.assertEqual(Click.objects.get().blocked_reason, "")

    @override_settings(TRAFFIC_FILTER_CHALLENGE=True)
    def test_challenge_rejects_forged_cookie(self):
        self.client.cookies["rc"] = "ok:forged"
        self.assertEqual(self.visit().status_code, 200)

    @override_settings(TRAFFIC_FILTER_CHALLENGE=True)
    def test_blocked_visits_skip_challenge(self):
        self.assertBlocked(self.visit(HTTP_USER_AGENT="curl/8.0"), "bot")


class DownloadTorExitNodesTests(SimpleTestCase):
    def test_saves_list(self):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        path = directory / "tor-exit-nodes.txt"
        body = b"198.51.100.2\n198.51.100.1\n198.51.100.1\n"
        with (
            self.settings(TOR_EXIT_NODES_PATH=path),
            mock.patch(
                "src.redirect.services.download_tor_exit_nodes.download_tor_exit_nodes_service.urlopen",
                return_value=io.BytesIO(body),
            ),
        ):
            self.assertEqual(DownloadTorExitNodesService().execute(), 2)
        self.assertEqual(path.read_text(), "198.51.100.1\n198.51.100.2\n")

    def test_refuses_empty_list(self):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        path = directory / "tor-exit-nodes.txt"
        path.write_text("198.51.100.1\n")
        with (
            self.settings(TOR_EXIT_NODES_PATH=path),
            mock.patch(
                "src.redirect.services.download_tor_exit_nodes.download_tor_exit_nodes_service.urlopen",
                return_value=io.BytesIO(b""),
            ),
            self.assertRaises(ValueError),
        ):
            DownloadTorExitNodesService().execute()
        self.assertEqual(path.read_text(), "198.51.100.1\n")


@override_settings(
    CLICK_IP_RETENTION_DAYS=7, BLOCKED_CLICK_RETENTION_DAYS=30, CLICK_RETENTION_DAYS=365
)
class CleanUpClicksTests(TestCase):
    def setUp(self):
        self.link = Link.objects.create(code="abc123", visits=4)

    def click(self, days_ago, blocked_reason=""):
        return Click.objects.create(
            link=self.link,
            ip="203.0.113.7",
            target_url="http://example.com",
            blocked_reason=blocked_reason,
            created_at=timezone.now() - timedelta(days=days_ago),
        )

    def test_applies_retention_periods(self):
        recent = self.click(1)
        old_ip = self.click(8)
        self.click(31, blocked_reason="bot")
        recent_blocked = self.click(29, blocked_reason="bot")
        self.click(366)

        result = CleanUpClicksService().execute()

        self.assertEqual(result, {"ips_cleared": 2, "blocked_deleted": 1, "allowed_deleted": 1})
        self.assertEqual(
            set(Click.objects.values_list("id", flat=True)), {recent.id, old_ip.id, recent_blocked.id}
        )
        old_ip.refresh_from_db()
        self.assertIsNone(old_ip.ip)
        self.assertEqual(old_ip.ip_hash, hash_ip("203.0.113.7"))
        recent.refresh_from_db()
        self.assertEqual(recent.ip, "203.0.113.7")
        self.link.refresh_from_db()
        self.assertEqual(self.link.visits, 4)

    @override_settings(
        CLICK_IP_RETENTION_DAYS=0, BLOCKED_CLICK_RETENTION_DAYS=0, CLICK_RETENTION_DAYS=0
    )
    def test_zero_keeps_everything(self):
        self.click(1000, blocked_reason="bot")
        self.assertEqual(
            CleanUpClicksService().execute(),
            {"ips_cleared": 0, "blocked_deleted": 0, "allowed_deleted": 0},
        )

    def test_management_command(self):
        self.click(400)
        out = io.StringIO()
        call_command("clean_up_clicks", stdout=out)
        self.assertIn("deleted 0 blocked and 1 allowed clicks", out.getvalue())


class HomeTests(TestCase):
    def test_homepage(self):
        response = self.client.get("/")
        self.assertContains(response, "Ad Redirector")
        self.assertContains(response, "GeoLite2 data created by MaxMind")
        self.assertContains(response, 'href="/privacy/"')
        self.assertNotContains(response, "privateplace")

    @override_settings(
        PRIVACY_OPERATOR_NAME="Example Ltd",
        PRIVACY_CONTACT_EMAIL="privacy@example.com",
        CLICK_IP_RETENTION_DAYS=7,
        BLOCKED_CLICK_RETENTION_DAYS=30,
        CLICK_RETENTION_DAYS=0,
    )
    def test_privacy_page(self):
        response = self.client.get("/privacy/")
        self.assertContains(response, "Example Ltd")
        self.assertContains(response, "mailto:privacy@example.com")
        self.assertContains(response, "deleted after 7 days")
        self.assertContains(response, "deleted after 30 days")
        self.assertContains(response, "not deleted automatically")
        self.assertContains(response, "GeoLite2 data created by MaxMind")


class AdminTests(TestCase):
    def test_old_admin_url_is_gone(self):
        self.assertEqual(self.client.get("/admin/").status_code, 404)


    def test_admin_requires_login(self):
        response = self.client.get("/privateplace/redirect/link/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/privateplace/login/", response["Location"])

    @override_settings(
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
    )
    def test_maxmind_attribution_in_footer(self):
        response = self.client.get("/privateplace/login/")
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
                MAXMIND_EDITION_IDS=["GeoLite2-City"],
                MAXMIND_DATABASE_DIR=self.directory,
            )
        )
        self.urlopen = self.enterContext(
            mock.patch("src.redirect.services.download_geoip_database.download_geoip_database_service.urlopen")
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

        self.assertTrue(DownloadGeoIPDatabaseService("GeoLite2-City").execute())

        self.assertEqual((self.directory / "GeoLite2-City.mmdb").read_bytes(), b"mmdb-data")
        request = self.urlopen.call_args.args[0]
        self.assertEqual(request.unredirected_hdrs["Authorization"], "Basic MTIzOnNlY3JldA==")

    def test_skips_download_when_unchanged(self):
        self.serve(geoip_archive(b"mmdb-data"))
        DownloadGeoIPDatabaseService("GeoLite2-City").execute()

        self.assertFalse(DownloadGeoIPDatabaseService("GeoLite2-City").execute())
        self.assertEqual(self.urlopen.call_count, 3)  # checksum + archive, then checksum only

    def test_rejects_checksum_mismatch(self):
        self.serve(geoip_archive(b"mmdb-data"), checksum="0" * 64)

        with self.assertRaises(ValueError):
            DownloadGeoIPDatabaseService("GeoLite2-City").execute()
        self.assertFalse((self.directory / "GeoLite2-City.mmdb").exists())

    def test_management_command(self):
        self.serve(geoip_archive(b"mmdb-data"))

        out = io.StringIO()
        call_command("download_geoip_database", stdout=out)
        self.assertIn("Installed", out.getvalue())

        out = io.StringIO()
        call_command("download_geoip_database", stdout=out)
        self.assertIn("Already up to date", out.getvalue())

    @override_settings(MAXMIND_LICENSE_KEY="")
    def test_requires_credentials(self):
        with self.assertRaises(ImproperlyConfigured):
            DownloadGeoIPDatabaseService("GeoLite2-City").execute()

