import json
import urllib.parse
import urllib.request

from django.utils.text import slugify

from .models import ConfiguracaoSite, IdentidadeExternaComentario


PROVIDER_LABELS = {
    IdentidadeExternaComentario.PROVIDER_ORCID: "ORCID",
    IdentidadeExternaComentario.PROVIDER_GITHUB: "GitHub",
    IdentidadeExternaComentario.PROVIDER_GOOGLE: "Google",
    IdentidadeExternaComentario.PROVIDER_CODEBERG: "Codeberg",
}


def oauth_provider_label(provider):
    return PROVIDER_LABELS.get(provider, provider.upper())


def _config_value(config, field_name, default=""):
    if not config:
        return default
    if hasattr(config, "get_runtime_setting"):
        value = config.get_runtime_setting(field_name, default=default)
    else:
        value = getattr(config, field_name, default)
    return value.strip() if isinstance(value, str) else value


def oauth_provider_enabled(config, provider):
    if not config:
        return False
    if provider == IdentidadeExternaComentario.PROVIDER_ORCID:
        return bool(_config_value(config, "oauth_orcid_client_id") and _config_value(config, "oauth_orcid_client_secret"))
    if provider == IdentidadeExternaComentario.PROVIDER_GITHUB:
        return bool(_config_value(config, "oauth_github_client_id") and _config_value(config, "oauth_github_client_secret"))
    if provider == IdentidadeExternaComentario.PROVIDER_GOOGLE:
        return bool(_config_value(config, "oauth_google_client_id") and _config_value(config, "oauth_google_client_secret"))
    if provider == IdentidadeExternaComentario.PROVIDER_CODEBERG:
        return bool(_config_value(config, "oauth_codeberg_client_id") and _config_value(config, "oauth_codeberg_client_secret"))
    return False


def oauth_provider_enabled_map(config):
    return {
        IdentidadeExternaComentario.PROVIDER_ORCID: oauth_provider_enabled(config, IdentidadeExternaComentario.PROVIDER_ORCID),
        IdentidadeExternaComentario.PROVIDER_GITHUB: oauth_provider_enabled(config, IdentidadeExternaComentario.PROVIDER_GITHUB),
        IdentidadeExternaComentario.PROVIDER_GOOGLE: oauth_provider_enabled(config, IdentidadeExternaComentario.PROVIDER_GOOGLE),
        IdentidadeExternaComentario.PROVIDER_CODEBERG: oauth_provider_enabled(config, IdentidadeExternaComentario.PROVIDER_CODEBERG),
    }


def _oauth_get(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _oauth_post(url, payload, headers=None):
    body = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers or {}, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _codeberg_base_url(config):
    return (_config_value(config, "oauth_codeberg_base_url", "https://codeberg.org") or "https://codeberg.org").rstrip("/")


def _oidc_discovery(base_url):
    return _oauth_get(base_url.rstrip("/") + "/.well-known/openid-configuration")


def oauth_build_authorize_url(config, provider, redirect_uri, state):
    if provider == IdentidadeExternaComentario.PROVIDER_ORCID:
        params = {
            "client_id": _config_value(config, "oauth_orcid_client_id"),
            "response_type": "code",
            "scope": "/authenticate",
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return "https://orcid.org/oauth/authorize?" + urllib.parse.urlencode(params)

    if provider == IdentidadeExternaComentario.PROVIDER_GITHUB:
        params = {
            "client_id": _config_value(config, "oauth_github_client_id"),
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
        return "https://github.com/login/oauth/authorize?" + urllib.parse.urlencode(params)

    if provider == IdentidadeExternaComentario.PROVIDER_GOOGLE:
        params = {
            "client_id": _config_value(config, "oauth_google_client_id"),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid profile email",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)

    if provider == IdentidadeExternaComentario.PROVIDER_CODEBERG:
        discovery = _oidc_discovery(_codeberg_base_url(config))
        params = {
            "client_id": _config_value(config, "oauth_codeberg_client_id"),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid profile email",
            "state": state,
        }
        return (discovery.get("authorization_endpoint") or (_codeberg_base_url(config) + "/login/oauth/authorize")) + "?" + urllib.parse.urlencode(params)

    raise ValueError("Provider OAuth desconhecido.")


def oauth_exchange_code(config, provider, code, redirect_uri):
    if provider == IdentidadeExternaComentario.PROVIDER_ORCID:
        return _oauth_post(
            "https://orcid.org/oauth/token",
            {
                "client_id": _config_value(config, "oauth_orcid_client_id"),
                "client_secret": _config_value(config, "oauth_orcid_client_secret"),
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )

    if provider == IdentidadeExternaComentario.PROVIDER_GITHUB:
        return _oauth_post(
            "https://github.com/login/oauth/access_token",
            {
                "client_id": _config_value(config, "oauth_github_client_id"),
                "client_secret": _config_value(config, "oauth_github_client_secret"),
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )

    if provider == IdentidadeExternaComentario.PROVIDER_GOOGLE:
        return _oauth_post(
            "https://oauth2.googleapis.com/token",
            {
                "client_id": _config_value(config, "oauth_google_client_id"),
                "client_secret": _config_value(config, "oauth_google_client_secret"),
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )

    if provider == IdentidadeExternaComentario.PROVIDER_CODEBERG:
        discovery = _oidc_discovery(_codeberg_base_url(config))
        return _oauth_post(
            discovery.get("token_endpoint") or (_codeberg_base_url(config) + "/login/oauth/access_token"),
            {
                "client_id": _config_value(config, "oauth_codeberg_client_id"),
                "client_secret": _config_value(config, "oauth_codeberg_client_secret"),
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )

    raise ValueError("Provider OAuth desconhecido.")


def oauth_fetch_profile(config, provider, token_data):
    if provider == IdentidadeExternaComentario.PROVIDER_ORCID:
        orcid_id = (token_data.get("orcid") or token_data.get("orcid_id") or "").strip()
        nome = (token_data.get("name") or "").strip()
        return {
            "provider": provider,
            "provider_user_id": orcid_id,
            "provider_username": orcid_id,
            "display_name": nome,
            "email": "",
            "email_verified": False,
            "profile_url": f"https://orcid.org/{orcid_id}" if orcid_id else "",
            "avatar_url": "",
            "scopes": token_data.get("scope") or "/authenticate",
            "orcid": orcid_id,
            "suggested_username": slugify(orcid_id or nome or "orcid")[:80],
            "raw": token_data,
        }

    access_token = (token_data.get("access_token") or "").strip()
    if not access_token:
        raise ValueError("Token OAuth ausente.")

    if provider == IdentidadeExternaComentario.PROVIDER_GITHUB:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "OwnPaper",
        }
        user_data = _oauth_get("https://api.github.com/user", headers=headers)
        emails = _oauth_get("https://api.github.com/user/emails", headers=headers)
        primary_email = ""
        primary_verified = False
        for item in emails:
            if item.get("primary"):
                primary_email = (item.get("email") or "").strip()
                primary_verified = bool(item.get("verified"))
                break
        if not primary_email and emails:
            primary_email = (emails[0].get("email") or "").strip()
            primary_verified = bool(emails[0].get("verified"))
        username = (user_data.get("login") or "").strip()
        return {
            "provider": provider,
            "provider_user_id": str(user_data.get("id") or ""),
            "provider_username": username,
            "display_name": (user_data.get("name") or username).strip(),
            "email": primary_email,
            "email_verified": primary_verified,
            "profile_url": (user_data.get("html_url") or "").strip(),
            "avatar_url": (user_data.get("avatar_url") or "").strip(),
            "scopes": token_data.get("scope") or "read:user user:email",
            "orcid": "",
            "suggested_username": slugify(username or user_data.get("name") or "github")[:80],
            "raw": {"token": token_data, "user": user_data, "emails": emails},
        }

    if provider == IdentidadeExternaComentario.PROVIDER_GOOGLE:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        user_data = _oauth_get("https://openidconnect.googleapis.com/v1/userinfo", headers=headers)
        email = (user_data.get("email") or "").strip()
        username_base = (
            user_data.get("preferred_username")
            or email.split("@")[0]
            or user_data.get("name")
            or "google"
        )
        return {
            "provider": provider,
            "provider_user_id": str(user_data.get("sub") or ""),
            "provider_username": slugify(username_base)[:80],
            "display_name": (user_data.get("name") or email or username_base).strip(),
            "email": email,
            "email_verified": bool(user_data.get("email_verified")),
            "profile_url": (user_data.get("profile") or "").strip(),
            "avatar_url": (user_data.get("picture") or "").strip(),
            "scopes": token_data.get("scope") or "openid profile email",
            "orcid": "",
            "suggested_username": slugify(username_base)[:80],
            "raw": {"token": token_data, "user": user_data},
        }

    if provider == IdentidadeExternaComentario.PROVIDER_CODEBERG:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        discovery = _oidc_discovery(_codeberg_base_url(config))
        userinfo_endpoint = discovery.get("userinfo_endpoint") or (_codeberg_base_url(config) + "/login/oauth/userinfo")
        user_data = _oauth_get(userinfo_endpoint, headers=headers)
        email = (user_data.get("email") or "").strip()
        username_base = (
            user_data.get("preferred_username")
            or user_data.get("nickname")
            or email.split("@")[0]
            or user_data.get("name")
            or "codeberg"
        )
        profile_url = ""
        if username_base:
            profile_url = _codeberg_base_url(config) + "/" + slugify(username_base)
        return {
            "provider": provider,
            "provider_user_id": str(user_data.get("sub") or ""),
            "provider_username": slugify(username_base)[:80],
            "display_name": (user_data.get("name") or email or username_base).strip(),
            "email": email,
            "email_verified": bool(user_data.get("email_verified")),
            "profile_url": profile_url,
            "avatar_url": (user_data.get("picture") or "").strip(),
            "scopes": token_data.get("scope") or "openid profile email",
            "orcid": "",
            "suggested_username": slugify(username_base)[:80],
            "raw": {"token": token_data, "user": user_data, "discovery": discovery},
        }

    raise ValueError("Provider OAuth desconhecido.")
