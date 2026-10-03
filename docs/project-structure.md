# Project structure

```
config/               Django settings, URLs, WSGI/ASGI
docs/                 Documentation (this folder)
src/                  Django apps, imported with the src. prefix (e.g. "src.redirect")
  redirect/
    models.py         Link (code, visits, created_at) and Click (link, ip, ip_hash, target_url, blocked_reason, created_at)
    views.py          Views: homepage (/) and redirect (/go/<code>/)
    templates/redirect/   base.html (layout, footer), home.html, privacy.html, challenge.html (JavaScript check page)
    services/         Business logic, one subfolder per service; the file is named after its class (ChallengeService → challenge_service.py)
      redirect/                 RedirectService: runs the filters and decides where a visit goes
      filtering/                All traffic filters, one <name>_filter_service.py per filter (see traffic-filtering.md)
      download_geoip_database/  Downloads the MaxMind databases
      download_tor_exit_nodes/  Downloads the Tor exit node list
      clean_up_clicks/          Applies the data retention periods
    tasks.py          Celery tasks
    management/commands/   download_geoip_database, download_tor_exit_nodes, clean_up_clicks (run the tasks by hand)
    admin.py          Admin for managing links and browsing clicks
    tests.py
templates/admin/base_site.html   Admin footer with the MaxMind attribution
Dockerfile, docker-compose.yml, docker-entrypoint.sh
make.sh               setup, deploy and build commands
docker/pgadmin/servers.json   pgAdmin's pre-registered connection to the db service
pyproject.toml, poetry.lock
.env.example
```
