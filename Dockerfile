FROM python:3.12-slim

# uv: dependency installer (pinned for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.6.3 /uv /uvx /bin/

# Editors for in-container code editing in air-gapped environments
RUN apt-get update \
    && apt-get install -y --no-install-recommends nano vim-tiny \
    && rm -rf /var/lib/apt/lists/*

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies only. The project itself is imported via PYTHONPATH
# (not installed as a package) so source edits take effect with no reinstall.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code and data
COPY . .

# Pre-build the local SQLite DB so the app runs fully offline
RUN /opt/venv/bin/python scripts/build_dwh_database.py --overwrite

EXPOSE 8501

CMD ["/opt/venv/bin/streamlit", "run", "src/interactive_ehr/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", \
     "--server.runOnSave=true", "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
