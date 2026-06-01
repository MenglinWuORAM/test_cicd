FROM python:3.11-slim AS base

WORKDIR /app

ENV PYTHONPATH=/app

COPY src/ ./src/


FROM base AS test

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tests/ ./tests/

CMD ["pytest", "--cov=src", "--cov-fail-under=80", "-v"]


FROM base AS prod

CMD ["python", "-c", "print('prod image built successfully')"]
