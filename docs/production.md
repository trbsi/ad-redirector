# Deploy to production (HTTPS)

`docker-compose.prod.yml` adds [nginx-proxy](https://github.com/nginx-proxy/nginx-proxy) (`ad-redirector-nginx-proxy`, ports 80/443) and [acme-companion](https://github.com/nginx-proxy/acme-companion) (`ad-redirector-acme-companion`), which gets a Let's Encrypt certificate for `DOMAIN` and renews it automatically. In this setup `web` is only reachable through nginx-proxy and logs the visitor IP that nginx-proxy appends to `X-Forwarded-For`. Local development doesn't use this file.

The quickest way: point the domain's DNS at the server, open ports 80 and 443, and run `./make.sh setup --prod`. It asks for the domain and Let's Encrypt email and does the steps below. Deploy updates later with `./make.sh deploy`.

To do it by hand:

1. Point `DOMAIN`'s DNS at the server and open ports 80 and 443.
2. In `.env`, set `DOMAIN`, `LETSENCRYPT_EMAIL`, `DJANGO_ALLOWED_HOSTS=<domain>` and `DJANGO_CSRF_TRUSTED_ORIGINS=https://<domain>`.
3. Start everything with both files:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

To avoid typing both files, add `COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml` to the server's `.env`; plain `docker compose` commands then include production.
