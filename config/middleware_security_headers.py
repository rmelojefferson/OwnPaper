from django.utils.deprecation import MiddlewareMixin


class OwnPaperSecurityHeadersMiddleware(MiddlewareMixin):
    """Add conservative browser hardening headers without breaking current runtime."""

    ADMIN_CONTENT_SECURITY_POLICY = "; ".join(
        [
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'self'",
            "img-src 'self' data: blob: https:",
            "font-src 'self' data: https:",
            "style-src 'self' 'unsafe-inline' https:",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:",
            "connect-src 'self' https:",
            "frame-src 'self' https://challenges.cloudflare.com https://www.youtube.com https://youtube.com https://www.youtube-nocookie.com",
            "media-src 'self' data: blob: https:",
            "worker-src 'self' blob:",
        ]
    )
    PUBLIC_CONTENT_SECURITY_POLICY = "; ".join(
        [
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'self'",
            "img-src 'self' data: blob: https:",
            "font-src 'self' data: https:",
            "style-src 'self' 'unsafe-inline' https:",
            "script-src 'self' 'unsafe-inline' https:",
            "connect-src 'self' https:",
            "frame-src 'self' https://challenges.cloudflare.com https://www.youtube.com https://youtube.com https://www.youtube-nocookie.com",
            "media-src 'self' data: blob: https:",
            "worker-src 'self' blob:",
        ]
    )

    PERMISSIONS_POLICY = ", ".join(
        [
            "accelerometer=()",
            "ambient-light-sensor=()",
            "autoplay=()",
            "camera=()",
            "display-capture=()",
            "fullscreen=(self)",
            "geolocation=()",
            "gyroscope=()",
            "magnetometer=()",
            "microphone=()",
            "midi=()",
            "payment=()",
            "publickey-credentials-get=(self)",
            "usb=()",
        ]
    )

    def process_response(self, request, response):
        path = getattr(request, "path", "") or ""
        csp = (
            self.ADMIN_CONTENT_SECURITY_POLICY
            if path.startswith(("/admin/", "/account/"))
            else self.PUBLIC_CONTENT_SECURITY_POLICY
        )
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("Permissions-Policy", self.PERMISSIONS_POLICY)
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return response
