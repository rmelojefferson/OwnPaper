FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    DJANGO_STATIC_ROOT=/app/static \
    DJANGO_MEDIA_ROOT=/app/media \
    PORT=8000

WORKDIR /app

RUN apt-get update --yes --quiet \
    && apt-get install --yes --quiet --no-install-recommends \
        build-essential \
        libcairo2 \
        libcairo2-dev \
        libjpeg62-turbo-dev \
        libpq-dev \
        libwebp-dev \
        netcat-openbsd \
        pkg-config \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash ownpaper

COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY --chown=ownpaper:ownpaper . /app

RUN mkdir -p /app/static /app/media \
    && chown -R ownpaper:ownpaper /app

USER ownpaper

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
