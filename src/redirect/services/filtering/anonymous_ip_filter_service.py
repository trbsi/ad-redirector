from geoip2.errors import AddressNotFoundError

from .geoip import reader

# Paid MaxMind database; this filter does nothing until it's added to MAXMIND_EDITION_IDS.
EDITION = "GeoIP2-Anonymous-IP"


class AnonymousIPFilterService:
    """Blocks VPNs, public and residential proxies, hosting providers and Tor (GeoIP2 Anonymous IP)."""

    reason = "anonymous_ip"

    def __init__(self, visit):
        self.visit = visit

    def matches(self):
        database = reader(EDITION) if self.visit.ip else None
        if database is None:
            return False
        try:
            return database.anonymous_ip(self.visit.ip).is_anonymous
        except AddressNotFoundError:
            return False
