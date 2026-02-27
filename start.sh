#!/bin/bash
# Démarrer Streamlit en arrière-plan
mkdir -p /tmp/nginx/client_body /tmp/nginx/proxy /tmp/nginx/fastcgi
uv run streamlit run main.py --server.port=8501 --server.address=localhost &
# Démarrer nginx au premier plan
nginx -g "daemon off;"