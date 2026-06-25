import ipaddress
import uuid

from django.conf import settings
from django.apps import apps
from django.utils import timezone
import psycopg


def ip_da_requisicao(request):
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def ip_ignorado_para_estatisticas(ip):
    ip = (ip or "").strip()
    if not ip:
        return False

    try:
        endereco = ipaddress.ip_address(ip)
    except ValueError:
        return False

    for item in getattr(settings, "OWNPAPER_ANALYTICS_EXCLUDED_IPS", []):
        item = str(item or "").strip()
        if not item:
            continue
        try:
            if "/" in item:
                if endereco in ipaddress.ip_network(item, strict=False):
                    return True
            elif endereco == ipaddress.ip_address(item):
                return True
        except ValueError:
            continue
    try:
        modelo = apps.get_model("conteudo", "IpDinamicoIgnoradoEstatisticas")
        if modelo.objects.filter(ip=str(endereco), expira_em__gt=timezone.now()).exists():
            return True
    except Exception:
        return False
    return False


def requisicao_ignorada_para_estatisticas(request):
    return ip_ignorado_para_estatisticas(ip_da_requisicao(request))


def sincronizar_ip_ignorado_plausible(ip, nome="rede-local"):
    if not getattr(settings, "OWNPAPER_PLAUSIBLE_IP_SYNC_ENABLED", False):
        return {"enabled": False, "updated": [], "missing": [], "error": ""}

    domains = list(getattr(settings, "OWNPAPER_PLAUSIBLE_SYNC_DOMAINS", []) or [])
    if not domains:
        return {"enabled": True, "updated": [], "missing": [], "error": "Nenhum domínio Plausible configurado."}

    description = f"OwnPaper dynamic exclude: {nome or 'rede-local'}"[:255]
    added_by = str(getattr(settings, "OWNPAPER_PLAUSIBLE_SYNC_ADDED_BY", "") or "OwnPaper")[:255]
    updated = []
    missing = []

    try:
        with psycopg.connect(
            dbname=getattr(settings, "OWNPAPER_PLAUSIBLE_DB_NAME", "plausible_db"),
            user=getattr(settings, "OWNPAPER_PLAUSIBLE_DB_USER", "postgres"),
            password=getattr(settings, "OWNPAPER_PLAUSIBLE_DB_PASSWORD", ""),
            host=getattr(settings, "OWNPAPER_PLAUSIBLE_DB_HOST", "plausible_db"),
            port=str(getattr(settings, "OWNPAPER_PLAUSIBLE_DB_PORT", "5432")),
            connect_timeout=5,
        ) as conn:
            with conn.cursor() as cur:
                for domain in domains:
                    domain = str(domain or "").strip()
                    if not domain:
                        continue
                    cur.execute("select id from sites where domain = %s", (domain,))
                    row = cur.fetchone()
                    if not row:
                        missing.append(domain)
                        continue
                    site_id = row[0]
                    cur.execute(
                        """
                        delete from shield_rules_ip
                        where site_id = %s and description = %s and inet <> %s::inet
                        """,
                        (site_id, description, ip),
                    )
                    cur.execute(
                        """
                        insert into shield_rules_ip
                            (id, site_id, inet, action, description, added_by, inserted_at, updated_at)
                        values
                            (%s, %s, %s::inet, 'deny', %s, %s, now(), now())
                        on conflict (site_id, inet) do update set
                            action = 'deny',
                            description = excluded.description,
                            added_by = excluded.added_by,
                            updated_at = excluded.updated_at
                        """,
                        (str(uuid.uuid4()), site_id, ip, description, added_by),
                    )
                    updated.append(domain)
            conn.commit()
    except Exception as exc:
        return {"enabled": True, "updated": updated, "missing": missing, "error": str(exc)}

    return {"enabled": True, "updated": updated, "missing": missing, "error": ""}
