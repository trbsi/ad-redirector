from django.conf import settings
from geoip2.errors import AddressNotFoundError

from .geoip import reader

EDITION = "GeoLite2-Country"


class CountryFilterService:
    """Blocks countries outside TRAFFIC_FILTER_ALLOWED_COUNTRIES or in TRAFFIC_FILTER_BLOCKED_COUNTRIES."""

    reason = "country"

    def __init__(self, visit):
        self.visit = visit

    def matches(self):
        allowed = settings.TRAFFIC_FILTER_ALLOWED_COUNTRIES
        blocked = settings.TRAFFIC_FILTER_BLOCKED_COUNTRIES
        if not (allowed or blocked) or not self.visit.ip:
            return False
        database = reader(EDITION)
        if database is None:
            return False

        try:
            country = database.country(self.visit.ip).country.iso_code
        except AddressNotFoundError:
            country = None
        if allowed and country not in allowed:
            return True
        return country in blocked
