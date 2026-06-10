FROM python:3.12-slim AS base
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

FROM base AS test
# Editable reinstall, easier for coverage checks
RUN pip install --no-cache-dir -e ".[dev]"
COPY tests/ ./tests/
COPY scripts/ ./scripts/
CMD ["pytest"]

# prod is package only.
FROM base AS prod
CMD ["python", "-c", "import quant_core; print('prod image ok:', quant_core.__name__)"]
