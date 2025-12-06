FROM python:3.11
WORKDIR /app

# --- build-time proxy wiring (provided via build args) ---
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY}

# Python quality-of-life
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=90

# (optional) install curl since your HEALTHCHECK uses it
# RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# deps
COPY requirements.txt .
# Force pip to use the proxy and PyPI simple index (more reliable)
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir \
      --proxy "${HTTPS_PROXY}" \
      -i https://pypi.org/simple \
      -r requirements.txt

# app
COPY . .

# non-root, perms (as you had)
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Healthcheck (uses curl installed above)
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
