# Third-Party Notices

OwnPaper is licensed under MIT. Third-party projects, packages, images and system libraries keep their own licenses.

This file is a technical license inventory for the current Docker/Python baseline. It is not legal advice. Anyone redistributing OwnPaper, publishing container images or offering it commercially should review the upstream licenses for their exact build.

For the complete Python environment inventory generated from the current container, see `docs/dependency-inventory.md`.

## Core Frameworks

| Component | Version/Baseline | License |
| --- | ---: | --- |
| Python | 3.12 Docker baseline | Python Software Foundation License |
| Django | 5.2.x | BSD-3-Clause |
| Wagtail | 7.4.x | BSD-3-Clause |
| PostgreSQL image | 16-alpine | PostgreSQL License plus Alpine package licenses |
| ClamAV image | stable | GPL-2.0 upstream license |
| Shlink image | stable, optional profile | MIT upstream license |
| Bulma CSS | 1.0.4 vendored CSS | MIT |

## Direct Python Dependencies

These are the direct Python dependencies declared in `requirements.txt` and observed in the current container environment.

| Package | Current observed version | License metadata |
| --- | ---: | --- |
| Django | 5.2.15 | BSD-3-Clause |
| wagtail | 7.4.2 | BSD-3-Clause |
| django-otp | 1.7.0 | Unlicense |
| django-two-factor-auth | 1.17.0 | MIT |
| gunicorn | 23.0.0 | MIT |
| phonenumberslite | 9.0.32 | Apache-2.0 |
| psycopg | 3.2.13 | LGPL-3.0-only |
| psycopg-binary | 3.2.13 | LGPL-3.0-only |
| whitenoise | 6.11.0 | MIT |
| xhtml2pdf | 0.2.17 | Apache-2.0 |
| pypdf | 6.13.3 | BSD-3-Clause |
| coloraide | 3.3.1 | MIT |
| cryptography | 48.0.1 | Apache-2.0 OR BSD-3-Clause |

## Important Transitive Python Dependencies

| Package | Observed version | License metadata |
| --- | ---: | --- |
| asgiref | 3.11.1 | BSD-3-Clause |
| sqlparse | 0.5.5 | BSD classifier |
| django-modelcluster | 6.5 | BSD-3-Clause |
| django-permissionedforms | 0.1 | BSD |
| django-taggit | 6.1.0 | BSD |
| django-treebeard | 5.2.2 | Apache-2.0 |
| djangorestframework | 3.17.1 | BSD-3-Clause |
| django-filter | 25.2 | BSD classifier |
| draftjs-exporter | 5.2.0 | MIT |
| Pillow | 12.2.0 | MIT-CMU |
| beautifulsoup4 | 4.15.0 | MIT |
| Willow | 1.12.0 | BSD classifier |
| requests | 2.34.2 | Apache-2.0 |
| openpyxl | 3.1.5 | MIT |
| anyascii | 0.3.3 | ISC |
| telepath | 0.3.1 | BSD |
| laces | 0.1.2 | BSD |
| django-tasks | 0.12.0 | BSD-3-Clause |
| modelsearch | 1.3.1 | BSD-3-Clause |
| qrcode | 7.4.2 | BSD |
| django-phonenumber-field | 8.4.0 | MIT |
| django-formtools | 2.6.1 | BSD |
| packaging | 26.2 | Apache-2.0 OR BSD-2-Clause |
| typing-extensions | 4.15.0 | PSF-2.0 |
| arabic-reshaper | 3.0.1 | MIT |
| html5lib | 1.1 | MIT |
| pyHanko | 0.35.1 | MIT |
| pyhanko-certvalidator | 0.31.1 | MIT |
| python-bidi | 0.6.10 | LGPL classifier |
| reportlab | 4.5.1 | BSD-style ReportLab license |
| svglib | 2.0.2 | LGPL-3.0-or-later |
| cffi | 2.0.0 | MIT |
| soupsieve | 2.8.4 | MIT |
| et-xmlfile | 2.0.0 | MIT |
| pypng | 0.20220715.0 | MIT |
| charset-normalizer | 3.4.7 | MIT |
| idna | 3.18 | BSD-3-Clause |
| urllib3 | 2.7.0 | MIT |
| certifi | 2026.6.17 | MPL-2.0 |
| filetype | 1.2.0 | MIT |
| defusedxml | 0.7.1 | PSF-style |
| pillow-heif | 1.4.0 | BSD-3-Clause metadata |
| pycparser | 3.0 | BSD-3-Clause |
| six | 1.17.0 | MIT |
| webencodings | 0.5.1 | BSD |
| asn1crypto | 1.5.1 | MIT |
| tzlocal | 5.4.3 | MIT |
| PyYAML | 6.0.3 | MIT |
| lxml | 6.1.1 | BSD-3-Clause |
| oscrypto | 1.3.0 | MIT |
| uritools | 6.1.2 | MIT |
| cssselect2 | 0.9.0 | BSD classifier |
| tinycss2 | 1.5.1 | BSD classifier |

## System Packages In The Docker Image

The Dockerfile installs Debian packages required for build/runtime support, including packages such as `build-essential`, `ffmpeg`, Cairo, JPEG/WebP/zlib/PQ development libraries, `netcat-openbsd` and `pkg-config`.

Those packages are not authored by OwnPaper. They are distributed under their respective Debian/upstream licenses. If you publish prebuilt container images, preserve the relevant license notices from the base image and installed packages.

## License Compatibility Notes

- OwnPaper application code is MIT.
- Django and Wagtail are permissively licensed and compatible with MIT distribution.
- LGPL dependencies such as `psycopg`, `svglib` and related libraries are used as external Python packages; keep their notices intact and do not misrepresent them as OwnPaper code.
- ClamAV is provided as a separate service image in Docker Compose. Its GPL-2.0 upstream license applies to ClamAV, not to OwnPaper's MIT application code merely because the services communicate over the network.
- Shlink is optional and runs under its own container/profile.
- Bulma is vendored as a CSS file and its MIT header is preserved in `config/static/vendor/bulma/bulma.min.css`.

## Sources Checked

- Local Python package metadata from the current Docker environment.
- `requirements.txt` and `Dockerfile` in this repository.
- Bulma vendored CSS header.
- Upstream license files for Shlink and ClamAV.
