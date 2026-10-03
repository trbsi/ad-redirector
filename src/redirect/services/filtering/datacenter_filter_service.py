import re

from django.conf import settings
from geoip2.errors import AddressNotFoundError

from .geoip import reader

EDITION = "GeoLite2-ASN"

# Cloud and hosting providers. Real visitors come from home and mobile networks.
# Cloudflare (13335) is left out: its WARP VPN is used by ordinary people.
HOSTING_ASNS = frozenset({
    16509, 14618,           # Amazon AWS
    396982, 15169, 19527,   # Google Cloud
    8075,                   # Microsoft Azure
    31898,                  # Oracle Cloud
    14061,                  # DigitalOcean
    24940, 213230,          # Hetzner
    16276,                  # OVH
    63949,                  # Akamai Linode
    20473,                  # Vultr
    51167,                  # Contabo
    12876,                  # Scaleway
    60781, 28753, 16265,    # Leaseweb
    9009,                   # M247
    45102,                  # Alibaba Cloud
    132203,                 # Tencent Cloud
    36352,                  # ColoCrossing
    46606,                  # Unified Layer
    26496,                  # GoDaddy
    197540,                 # netcup
})

HOSTING_KEYWORDS = re.compile(
    r"hosting|datacenter|data center|\bvps\b|dedicated|colocation|server", re.IGNORECASE
)


class DatacenterFilterService:
    """Blocks IPs that belong to cloud and hosting providers, using the GeoLite2-ASN database."""

    reason = "datacenter"

    def __init__(self, visit):
        self.visit = visit

    def matches(self):
        database = reader(EDITION) if self.visit.ip else None
        if database is None:
            return False
        try:
            network = database.asn(self.visit.ip)
        except AddressNotFoundError:
            return False

        blocked = HOSTING_ASNS | settings.TRAFFIC_FILTER_EXTRA_BLOCKED_ASNS
        if network.autonomous_system_number in blocked:
            return True
        return bool(HOSTING_KEYWORDS.search(network.autonomous_system_organization or ""))
