FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/milaan/backend
COPY milaan/backend/requirements.txt milaan/backend/constraints-py312.txt /tmp/
# Optional trusted CA bundle for enterprise/managed build proxies; never disable TLS.
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then PIP_CERT=/run/secrets/build_ca pip install --no-cache-dir -c /tmp/constraints-py312.txt -r /tmp/requirements.txt; else pip install --no-cache-dir -c /tmp/constraints-py312.txt -r /tmp/requirements.txt; fi \
    && useradd --uid 10001 --create-home milaan
COPY milaan/backend/app ./app
COPY milaan/backend/matching ./matching
COPY milaan/backend/migrations ./migrations
COPY milaan/backend/alembic.ini ./alembic.ini
COPY milaan/frontend/dist /app/milaan/frontend/dist
RUN mkdir -p /app/data/uploads && chown -R milaan:milaan /app
USER milaan
ENV DATABASE_URL=sqlite:////app/data/milaan.db STORAGE_DIR=/app/data/uploads
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["sh","-c","python -m alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
