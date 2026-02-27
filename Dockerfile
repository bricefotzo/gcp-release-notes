# syntax=docker/dockerfile:1

# Comments are provided throughout this file to help you get started.
# If you need more help, visit the Dockerfile reference guide at
# https://docs.docker.com/go/dockerfile-reference/

# Want to help us make this template better? Share your feedback here: https://forms.gle/ybq9Krt8jtBL3iCk7

ARG PYTHON_VERSION=3.12-bookworm
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-slim as base

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create a non-privileged user that the app will run under.
# See https://docs.docker.com/go/dockerfile-user-best-practices/
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/home/appuser" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser \
    && mkdir -p /home/appuser/.cache/uv \
    && chown -R appuser:appuser /home/appuser

# Installer nginx
RUN apt-get update && apt-get install -y nginx curl && rm -rf /var/lib/apt/lists/*
# Supprimer les configs par défaut de nginx
RUN rm -f /etc/nginx/conf.d/default.conf /etc/nginx/sites-enabled/default
# Download dependencies as a separate step to take advantage of Docker's caching.
# Leverage a cache mount to /root/.cache/pip to speed up subsequent builds.
# Leverage a bind mount to requirements.txt to avoid having to copy them into
# into this layer.
RUN --mount=type=cache,target=/home/appuser/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

# Switch to the non-privileged user to run the application.
USER appuser

# Copy the source code into the container.

COPY nginx.conf /etc/nginx/nginx.conf
COPY start.sh .
COPY . .
# Expose the port that the application listens on.
EXPOSE 8080

# Run the application.
CMD ["./start.sh"]

