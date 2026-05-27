FROM python:3.13
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY tests ./tests
COPY conftest.py ./

RUN useradd app && chown -R app:app /app
USER app
CMD ["pytest", "-v"]