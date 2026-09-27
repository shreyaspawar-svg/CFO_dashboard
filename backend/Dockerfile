FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Shell form (not the JSON array form) so $PORT is actually expanded --
# Render (and most PaaS hosts) inject a dynamic $PORT and expect the
# container to bind to it; 8000 is only the local/docker-compose default.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
