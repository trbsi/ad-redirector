# How it works

- **Homepage:** `/` shows a short page explaining the service, with the MaxMind attribution. It doesn't link to the admin.
- **Privacy page:** `/privacy/` explains what is recorded, why, how long it's kept, the cookie and visitors' rights. The retention periods shown come from the settings. Set `PRIVACY_OPERATOR_NAME` and `PRIVACY_CONTACT_EMAIL` before going live. It's linked from the homepage and the JavaScript check page.
- **Managing links:** log in to the Django admin at `/privateplace/` and add a link under *Links*. Codes must be lowercase letters and digits (e.g. `3484x2z2w2a4u4q2r28463o5111`) and must be unique. The list shows each link's visit count and its direct URL.
- **Redirecting:** `GET /go/<code>/` runs the [traffic filters](traffic-filtering.md). A visit that passes increments the link's visit count, records a `Click`, and gets a `302` to the JuicyAds URL. Unknown codes return `404`. Responses are sent with no-cache headers.
- **GeoIP databases:** every day at 03:00 UTC, Celery beat queues `download_geoip_database`, which downloads each edition in `MAXMIND_EDITION_IDS` (GeoLite2-Country and GeoLite2-ASN by default). It checks MaxMind's published SHA-256 first and only downloads when a new release is out, verifies the archive, and atomically replaces `<edition>.mmdb`. Run it immediately with `python manage.py download_geoip_database` (locally: `poetry run python manage.py download_geoip_database`, saves to `geoip/`; in Docker: `docker compose exec celery-worker python manage.py download_geoip_database`). The GeoLite2 license requires the attribution shown in the admin footer.
- **Tor exit nodes:** every hour, `download_tor_exit_nodes` saves the Tor Project's exit node list to `tor-exit-nodes.txt` next to the MaxMind databases. Run it by hand with `python manage.py download_tor_exit_nodes`.
- **Clicks:** browse and filter them under *Clicks* in the admin (read-only). Filter by *blocked reason* to see what each traffic filter blocked.
- **Personal data (GDPR):** each click stores the visitor IP and a keyed hash of it (`ip_hash`, HMAC with `DJANGO_SECRET_KEY`). Every day at 04:00 UTC, `clean_up_clicks`:
  - clears full IPs older than `CLICK_IP_RETENTION_DAYS` (7); the hash stays, so the repeat-click check keeps working
  - deletes blocked clicks older than `BLOCKED_CLICK_RETENTION_DAYS` (30)
  - deletes successful clicks older than `CLICK_RETENTION_DAYS` (365); link visit counts are stored separately and don't change

  Run it by hand with `python manage.py clean_up_clicks`. Changing `DJANGO_SECRET_KEY` changes the hashes, so visitors from before the change aren't recognized as repeat clicks.
