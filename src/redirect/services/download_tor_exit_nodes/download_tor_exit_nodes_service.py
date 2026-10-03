import ipaddress
import os
import tempfile
from urllib.request import urlopen

from django.conf import settings

DOWNLOAD_URL = "https://check.torproject.org/torbulkexitlist"


class DownloadTorExitNodesService:
    """Saves the Tor Project's current list of exit node IPs to TOR_EXIT_NODES_PATH."""

    def execute(self):
        """Return the number of addresses saved."""
        with urlopen(DOWNLOAD_URL, timeout=60) as response:
            lines = response.read().decode().split()
        addresses = sorted({str(ipaddress.ip_address(line)) for line in lines})
        if not addresses:
            # Keep the previous list rather than replace it with nothing.
            raise ValueError("Tor exit node list is empty")

        path = settings.TOR_EXIT_NODES_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write next to the target so the final rename is atomic.
        with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as f:
            f.write("\n".join(addresses) + "\n")
        os.replace(f.name, path)
        return len(addresses)
