# Security Policy

OwnPaper is a self-hosted Django/Wagtail application. Security depends on both the application code and the operator's infrastructure.

## Supported Version

There is no formal long-term support program. Security fixes are expected to target the current main branch used by the maintainer's active installations.

Fork maintainers are responsible for their own supported versions.

## Reporting A Vulnerability

Do not publish sensitive exploit details in a public issue.

Preferred disclosure flow:

1. Use GitHub private vulnerability reporting if it is enabled for the repository.
2. If it is not enabled, open a minimal public issue stating that you found a security concern and request a private contact path.
3. Do not include credentials, personal data, database dumps, backup files or exploit payloads in public channels.

## Operational Requirements

Before production use, operators should configure:

- HTTPS and a trusted reverse proxy;
- strong `DJANGO_SECRET_KEY`;
- restricted `DJANGO_ALLOWED_HOSTS` and CSRF origins;
- PostgreSQL credentials stored outside Git;
- SMTP credentials stored outside Git;
- two-factor authentication for admin users;
- ClamAV enabled for upload scanning;
- backup storage outside the application container when possible;
- retention policies for logs, raw statistics and exports;
- OS/container image updates;
- server-level firewall and monitoring.

## Known Security Boundaries

- Hash-chained audit logs are tamper-evident at application level, not a replacement for append-only external logging or immutable infrastructure.
- Malware scanning reduces risk but does not guarantee that every malicious file will be detected.
- Internal statistics are intended as a lightweight preview, not a full analytics/security-monitoring platform.
- External analytics scripts should only be configured by trusted operators and should be reviewed against the site's privacy policy.
