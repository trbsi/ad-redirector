# Traffic filtering

Each check is a service in `src/redirect/services/filtering/<name>_filter_service.py`. They run in this order, and the first one that matches blocks the visit:

| Filter | Blocked reason | Blocks | Needs |
|---|---|---|---|
| `preview_crawler` | `preview_crawler` | Link-preview fetches from WhatsApp, Telegram, Facebook, X, Slack, Discord, LinkedIn… | — |
| `bot` | `bot` | Bot/tool User-Agents (curl, python-requests, headless browsers, crawlers), or a missing `User-Agent`, `Accept` or `Accept-Language` | — |
| `country` | `country` | Countries outside `TRAFFIC_FILTER_ALLOWED_COUNTRIES` or in `TRAFFIC_FILTER_BLOCKED_COUNTRIES`. With an allow list, IPs whose country is unknown are blocked too | GeoLite2-Country |
| `datacenter` | `datacenter` | Cloud and hosting networks (AWS, Google Cloud, Azure, DigitalOcean, Hetzner, OVH…), plus `TRAFFIC_FILTER_EXTRA_BLOCKED_ASNS` and network names containing "hosting", "server", "VPS"… | GeoLite2-ASN |
| `anonymous_ip` | `anonymous_ip` | VPNs, public and residential proxies | GeoIP2-Anonymous-IP (paid; add it to `MAXMIND_EDITION_IDS`) |
| `tor_exit_node` | `tor` | Tor exit nodes | Tor exit node list |
| `repeat_click` | `repeat_click` | An IP that already went through the same link within `TRAFFIC_FILTER_REPEAT_CLICK_HOURS` | — |

- **Blocked visits** are logged as a `Click` with the reason, aren't counted in the link's visits, and are sent to `TRAFFIC_FILTER_BLOCKED_URL` (the homepage by default).
- **JavaScript check** (`filtering/challenge_service.py`): a visit that passes the filters first gets a small page that sets a signed cookie with JavaScript and reloads. Bots that don't run JavaScript never get through. The cookie lasts 30 days, so real visitors see the page once. Turn it off with `TRAFFIC_FILTER_CHALLENGE=0`.
- **Missing data:** if a database or the Tor list hasn't been downloaded yet, the filters that need it let visits through, and a warning is logged.
- **Trying the rules out:** set `TRAFFIC_FILTER_LOG_ONLY=1` to let every visit through while still recording in *blocked reason* what would have been blocked.
