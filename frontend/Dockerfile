FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y nginx curl && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/conf.d/default.conf /etc/nginx/sites-enabled/default

COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY nginx.conf /etc/nginx/nginx.conf

COPY . .
RUN chmod +x /app/start.sh

EXPOSE 8080

CMD ["bash", "/app/start.sh"]
