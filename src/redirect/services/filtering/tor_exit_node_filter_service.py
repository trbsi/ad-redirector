from django.conf import settings

# Loaded addresses, keyed by the file's path and mtime so a new download is picked up.
_cache = {"key": None, "addresses": frozenset()}


def exit_nodes():
    path = settings.TOR_EXIT_NODES_PATH
    try:
        key = (path, path.stat().st_mtime)
    except FileNotFoundError:
        return frozenset()
    if _cache["key"] != key:
        _cache["addresses"] = frozenset(path.read_text().split())
        _cache["key"] = key
    return _cache["addresses"]


class TorExitNodeFilterService:
    """Blocks Tor exit nodes, from the list the download_tor_exit_nodes task keeps up to date."""

    reason = "tor"

    def __init__(self, visit):
        self.visit = visit

    def matches(self):
        return self.visit.ip in exit_nodes()
