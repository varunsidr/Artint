# Browser assets match the pinned Python Playwright package. Only Chromium
# assets enter the runtime; the upstream image is a build-time source, not the runtime.
FROM mcr.microsoft.com/playwright/python:v1.64.1-noble@sha256:330d401ae23c905896a0c26c66c36fc971b621519e7b11b435a8328d7bf6e031 AS browser-assets

# Python 3.13.14, official multi-architecture manifest, resolved 2026-10-28.
FROM python:3.13.14-slim-bookworm@sha256:67a1e1f215ccda113cfc024e8639049257e88f273898f595b61476d128d387e8 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    ARTICLE_BROWSER_CHANNEL=chromium \
    ARTICLE_LIBRARY_DB=/var/lib/artint/data/articles.db \
    ARTICLE_PDF_DIR=/var/lib/artint/pdfs \
    HOME=/tmp/artint-home \
    XDG_CACHE_HOME=/tmp/artint-cache \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app
COPY requirements.txt requirements-linux-lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements-linux-lock.txt \
    && python -m pip check \
    && python -m playwright install-deps chromium \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 artint \
    && useradd --uid 10001 --gid artint --no-create-home --home-dir /tmp/artint-home artint \
    && mkdir -p /var/lib/artint/data /var/lib/artint/pdfs \
    && chown -R artint:artint /var/lib/artint

COPY --from=browser-assets /ms-playwright/chromium-1248/ /opt/playwright/chromium-1248/
COPY --from=browser-assets /ms-playwright/chromium_headless_shell-1248/ /opt/playwright/chromium_headless_shell-1248/
COPY --from=browser-assets /ms-playwright/ffmpeg-1013/ /opt/playwright/ffmpeg-1013/

COPY app/ ./app/
COPY scripts/seed_demo.py scripts/check_install.py scripts/smoke_install.py ./scripts/
COPY .streamlit/config.toml ./.streamlit/config.toml
COPY cli.py LICENSE ./

USER artint
EXPOSE 8501
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=4 \
    CMD ["python", "scripts/check_install.py", "--health-url", "http://127.0.0.1:8501/_stcore/health"]
CMD ["python", "-m", "streamlit", "run", "app/dashboard.py", "--server.address", "0.0.0.0", "--server.port", "8501"]

# Explicit test target; test dependencies and fixtures stay out of the runtime image.
FROM runtime AS test
USER root
COPY requirements-dev.txt ./
RUN python -m pip install --no-cache-dir -r requirements-dev.txt && python -m pip check
COPY tests/ ./tests/
COPY scripts/evaluate_extraction.py ./scripts/
USER artint
ENV RUN_BROWSER_TESTS=1
HEALTHCHECK NONE
CMD ["python", "-m", "pytest", "-q", "tests"]

# A plain `docker build .` also produces the runtime, not the test image.
FROM runtime AS final
