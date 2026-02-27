#!/bin/bash
set -e

mkdir -p /tmp/nginx/client_body /tmp/nginx/proxy /tmp/nginx/fastcgi

# Démarrer Streamlit en arrière-plan
uv run streamlit run main.py --server.port=8501 --server.address=127.0.0.1 &

# Attendre que Streamlit soit prêt
echo "Waiting for Streamlit to start..."
until curl -s http://127.0.0.1:8501/_stcore/health > /dev/null 2>&1; do
    sleep 1
done
echo "Streamlit is up!"

# Démarrer nginx au premier plan
nginx -g "daemon off;"