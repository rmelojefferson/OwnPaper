import ipaddress

from django.conf import settings


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
    return False


def requisicao_ignorada_para_estatisticas(request):
    return ip_ignorado_para_estatisticas(ip_da_requisicao(request))
