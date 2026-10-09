FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY backend/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir pip==26.2.1 \
    && pip install --no-cache-dir -r /app/requirements.lock
COPY backend/ /app/backend/
WORKDIR /app/backend

# Django, Airflow, and Spark share analytics files through a named volume.
# UID/GID 20000 is the explicit shared-volume group for the development stack.
RUN groupadd --gid 20000 assetflow-analytics \
    && useradd --uid 10001 --gid 20000 --create-home --shell /usr/sbin/nologin assetflow \
    && mkdir -p /srv/assetflow/analytics /srv/assetflow/private /srv/assetflow/static /app/backend/private_media \
    && chown -R assetflow:assetflow-analytics /srv/assetflow/analytics /srv/assetflow/private /srv/assetflow/static /app/backend/private_media \
    && chmod 2770 /srv/assetflow/analytics /srv/assetflow/private /app/backend/private_media \
    && chmod 2775 /srv/assetflow/static

USER 10001:20000

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
