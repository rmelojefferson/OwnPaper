# HTTPS e proxy reverso

OwnPaper deve rodar atrás de um proxy reverso HTTPS, como Nginx, Caddy, Traefik ou serviço equivalente do provedor.

Este documento usa Nginx como exemplo. Ajuste caminhos, portas e domínio conforme sua instalação.

## Princípios

- use um domínio próprio para o OwnPaper;
- não compartilhe o mesmo virtual host HTTPS com outra aplicação;
- sirva `/static/` e `/media/` pelo proxy quando possível;
- repasse corretamente `Host`, IP real e protocolo para o Django;
- ative redirecionamento HTTPS e HSTS somente depois de validar o certificado.

## Exemplo de Nginx HTTP

Use este bloco antes de emitir o certificado ou quando precisar validar ACME/Let's Encrypt:

```nginx
server {
    listen 80;
    server_name exemplo.com www.exemplo.com;

    client_max_body_size 600m;

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
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Exemplo de Nginx HTTPS

Depois de emitir o certificado:

```nginx
server {
    listen 443 ssl http2;
    server_name exemplo.com www.exemplo.com;

    ssl_certificate /etc/letsencrypt/live/exemplo.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/exemplo.com/privkey.pem;

    client_max_body_size 600m;

    location /static/ {
        alias /var/www/ownpaper/static/;
    }

    location /media/ {
        alias /var/www/ownpaper/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Opcionalmente redirecione HTTP para HTTPS:

```nginx
server {
    listen 80;
    server_name exemplo.com www.exemplo.com;
    return 301 https://$host$request_uri;
}
```

## Variáveis Django recomendadas

```env
DJANGO_ALLOWED_HOSTS=exemplo.com,www.exemplo.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://exemplo.com,https://www.exemplo.com
DJANGO_WAGTAILADMIN_BASE_URL=https://exemplo.com
OWNPAPER_PUBLIC_BASE_URL=https://exemplo.com
DJANGO_SECURE_PROXY_SSL_HEADER=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
```

Depois de confirmar que HTTPS está estável:

```env
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SECURE_HSTS_SECONDS=31536000
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=false
DJANGO_SECURE_HSTS_PRELOAD=false
```

Não habilite `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=true` nem `DJANGO_SECURE_HSTS_PRELOAD=true` até ter certeza de que todos os subdomínios relevantes usam HTTPS corretamente.

## Checklist de segurança

Antes de alterar o proxy:

```bash
sudo nginx -T > /root/nginx-before-ownpaper.txt
```

Depois de editar:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Valide:

```bash
curl -I https://exemplo.com/
curl -I http://exemplo.com/
```

Se houver outra aplicação no mesmo servidor, mantenha cada aplicação em um `server_name` próprio para evitar que o tráfego HTTPS caia no virtual host errado.
