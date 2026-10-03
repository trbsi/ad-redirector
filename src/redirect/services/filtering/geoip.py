import logging
from pathlib import Path

import geoip2.database
from django.conf import settings

logger = logging.getLogger(__name__)

# Open readers by path, with the file's mtime so a new download is picked up.
_readers = {}
_reported_missing = set()


def reader(edition):
    """Return a reader for a downloaded MaxMind database, or None if it isn't there."""
    path = Path(settings.MAXMIND_DATABASE_DIR) / f"{edition}.mmdb"
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        if edition not in _reported_missing:
            _reported_missing.add(edition)
            logger.warning("%s not found; filters that need it are skipped", path)
        return None

    cached = _readers.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    opened = geoip2.database.Reader(str(path))
    _readers[path] = (mtime, opened)
    return opened
