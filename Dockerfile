
FROM python:3.11-slim AS base
WORKDIR /app
COPY src/ ./src/
 

FROM base AS test
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY tests/ ./tests/

CMD ["pytest", "--cov=src", "--cov-fail-under=80", "-v"]
 
