# syntax=docker/dockerfile:1

# ---------- Stage 1: builder ----------
FROM python:3.12-slim-bookworm AS builder
WORKDIR /build
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# dependency dulu (jarang berubah) -> layer cache termanfaatkan
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app

RUN useradd --system --no-create-home appuser

# ambil hanya venv hasil build, tanpa pip cache dan tools build
COPY --from=builder /opt/venv /opt/venv
# source code terakhir (paling sering berubah)
COPY app/ ./

USER appuser
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "app:app"]