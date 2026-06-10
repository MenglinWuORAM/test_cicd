# Multi-stage build. The local self-hosted runner builds these on its own
# Docker daemon; no registry is involved.

FROM python:3.12-slim AS base
WORKDIR /app
# Install the package so quant_core is importable. The src layout means the
# real files live under /app/src, which is what coverage will record.
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

# ---- test: dev deps + tests + the selection script ----
FROM base AS test
# Editable reinstall so quant_core resolves to /app/src (not site-packages):
# coverage then records "src/quant_core/..." paths that match the git checkout.
RUN pip install --no-cache-dir -e ".[dev]"
COPY tests/ ./tests/
COPY scripts/ ./scripts/
CMD ["pytest"]

# ---- prod: clean runtime image, package only ----
FROM base AS prod
# Sanity import so a broken build fails immediately. Real daily jobs override
# this CMD (e.g. `docker run selection-demo:latest python -m my_job`).
CMD ["python", "-c", "import quant_core; print('prod image ok:', quant_core.__name__)"]
