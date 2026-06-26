import ipaddress
import hashlib
import re

from django.conf import settings
from django.apps import apps
from django.core.cache import cache
from django.utils import timezone

BOT_USER_AGENT_PATTERNS = [
    r"\b(bot|crawler|spider|slurp)\b",
    r"googlebot|bingbot|duckduckbot|baiduspider|yandexbot",
    r"adsbot|mediapartners-google|googleother|apis-google",
    r"facebookexternalhit|twitterbot|linkedinbot|whatsapp|telegrambot|discordbot|slackbot",
    r"amazonbot|petalbot|bytespider|semrushbot|ahrefsbot|mj12bot|dotbot",
    r"headlesschrome|phantomjs|selenium|playwright|puppeteer|nightmare|cypress",
    r"python-requests|python-urllib|httpx|aiohttp|curl|wget|libwww-perl|go-http-client|okhttp",
    r"scrapy|zgrab|masscan|nikto|nmap|sqlmap",
]

SUSPICIOUS_USER_AGENT_PATTERNS = [
    r"windows nt 6\.1;.*firefox/47\.0",
    r"android 16;.*firefox/149\.0",
]


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


def user_agent_ignorado_para_estatisticas(user_agent):
    if not getattr(settings, "OWNPAPER_ANALYTICS_BLOCK_BOTS", True):
        return False

    user_agent = str(user_agent or "").strip()
    if not user_agent:
        return True

    patterns = (
        BOT_USER_AGENT_PATTERNS
        + SUSPICIOUS_USER_AGENT_PATTERNS
        + list(getattr(settings, "OWNPAPER_ANALYTICS_BLOCKED_USER_AGENT_PATTERNS", []) or [])
    )
    for pattern in patterns:
        try:
            if re.search(pattern, user_agent, flags=re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


def _fingerprint_excedeu_limite(request, ip):
    if not getattr(settings, "OWNPAPER_ANALYTICS_FINGERPRINT_THROTTLE_ENABLED", True):
        return False
    if str(getattr(request, "method", "GET") or "GET").upper() != "GET":
        return False

    try:
        limite = int(getattr(settings, "OWNPAPER_ANALYTICS_FINGERPRINT_THROTTLE_MAX_HITS", 5))
        ttl = int(getattr(settings, "OWNPAPER_ANALYTICS_FINGERPRINT_THROTTLE_SECONDS", 60 * 60 * 6))
    except (TypeError, ValueError):
        limite = 5
        ttl = 60 * 60 * 6

    if limite < 1 or ttl < 1:
        return False

    user_agent = str(request.META.get("HTTP_USER_AGENT") or "").strip()
    path = str(getattr(request, "path", "") or "").split("?", 1)[0]
    raw = f"{ip}|{user_agent}|{path}".encode("utf-8", errors="ignore")
    key = "ownpaper:analytics:fingerprint:" + hashlib.sha256(raw).hexdigest()

    try:
        atual = cache.get(key)
        if atual is None:
            cache.set(key, 1, ttl)
            return False
        atual = int(atual)
        if atual >= limite:
            return True
        cache.incr(key)
    except Exception:
        return False
    return False


def requisicao_ignorada_para_estatisticas(request):
    ip = ip_da_requisicao(request)
    if ip_ignorado_para_estatisticas(ip):
        return True
    if user_agent_ignorado_para_estatisticas(request.META.get("HTTP_USER_AGENT") or ""):
        return True
    return _fingerprint_excedeu_limite(request, ip)
