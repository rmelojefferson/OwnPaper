# HTTPS Without Interrupting Plausible

This note documents the current test-server situation for `teste.keepsound.com.br`
and how to enable HTTPS tests for OwnPaper without taking the existing Plausible
service offline.

## Current Observation

The Django/Wagtail test app responds over HTTP:

```text
http://teste.keepsound.com.br/
```

The HTTPS endpoint currently does not serve the same app. A certificate check
for `https://teste.keepsound.com.br/` fails because the certificate does not
cover that host. When certificate verification is bypassed, the HTTPS response
is a Plausible page. That means nginx or another reverse proxy is routing port
443 for this host to Plausible, not to OwnPaper.

The current Plausible hostname is:

```text
https://analytics.keepsound.com.br/
```

The likely issue is that the nginx HTTPS server block for Plausible is also
acting as the default TLS server for requests that do not match a specific
`teste.keepsound.com.br` HTTPS block.

## Recommended Approach

Do not reuse the same HTTPS virtual host for both Plausible and OwnPaper.
Keep Plausible on its own hostname and give OwnPaper its own hostname.

Example:

```text
analytics.keepsound.com.br -> Plausible
teste.keepsound.com.br     -> OwnPaper test app
```

or:

```text
plausible.keepsound.com.br -> Plausible
ownpaper-test.keepsound.com.br -> OwnPaper test app
```

Both can share the same server and the same ports `80` and `443`. The reverse
proxy decides where traffic goes by `server_name`.

## Nginx Shape

Use separate server blocks.

Plausible keeps its current block:

```nginx
server {
    listen 443 ssl http2;
    server_name analytics.keepsound.com.br;

    ssl_certificate /etc/letsencrypt/live/analytics.keepsound.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/analytics.keepsound.com.br/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

OwnPaper gets a separate block:

```nginx
server {
    listen 80;
    server_name teste.keepsound.com.br;

    client_max_body_size 50m;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location /static/ {
        alias /var/www/ownpaper/static/;
    }

    location /media/ {
        alias /var/www/ownpaper/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:18080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

After a certificate exists for `teste.keepsound.com.br`, add the HTTPS block
and optionally redirect HTTP to HTTPS:

```nginx

server {
    listen 443 ssl http2;
    server_name teste.keepsound.com.br;

    ssl_certificate /etc/letsencrypt/live/teste.keepsound.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/teste.keepsound.com.br/privkey.pem;

    client_max_body_size 50m;

    location /static/ {
        alias /var/www/ownpaper/static/;
    }

    location /media/ {
        alias /var/www/ownpaper/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:18080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

The upstream ports above are examples. Keep whatever port Plausible already
uses, and point OwnPaper to the port where Gunicorn/Django is actually running.

## Certificate Flow

1. Confirm DNS for the OwnPaper hostname points to the server.
2. Add the nginx HTTP server block for the OwnPaper hostname.
3. Test nginx configuration:

```bash
sudo nginx -t
```

4. Reload nginx:

```bash
sudo systemctl reload nginx
```

5. Issue a certificate for the OwnPaper hostname:

```bash
sudo certbot --nginx -d teste.keepsound.com.br
```

6. Confirm Plausible still responds on its own hostname.
7. Confirm OwnPaper responds over HTTPS:

```bash
curl -I https://teste.keepsound.com.br/
```

## Django Settings Needed For HTTPS

For a production-like HTTPS test, Django should know it is behind a proxy:

```text
DJANGO_ALLOWED_HOSTS=teste.keepsound.com.br
DJANGO_CSRF_TRUSTED_ORIGINS=https://teste.keepsound.com.br
DJANGO_WAGTAILADMIN_BASE_URL=https://teste.keepsound.com.br
DJANGO_SECURE_PROXY_SSL_HEADER=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
```

Once HTTPS is stable, enable redirect and HSTS carefully:

```text
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SECURE_HSTS_SECONDS=31536000
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=false
DJANGO_SECURE_HSTS_PRELOAD=false
```

Do not enable `SECURE_HSTS_INCLUDE_SUBDOMAINS` unless every subdomain that
matters is ready for HTTPS.

## Safe Testing Checklist

Before changing nginx:

```bash
sudo nginx -T > /root/nginx-before-ownpaper-https.txt
```

After editing:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Validate both services:

```bash
curl -I https://analytics.keepsound.com.br/
curl -I https://teste.keepsound.com.br/
curl -I http://teste.keepsound.com.br/
```

Rollback is usually just restoring the previous nginx config and reloading
nginx. Avoid stopping containers or services unless the proxy configuration
itself is not enough.
