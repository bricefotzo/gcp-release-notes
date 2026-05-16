#!/bin/bash
set -e

mkdir -p /tmp/nginx/client_body /tmp/nginx/proxy /tmp/nginx/fastcgi

# Start Streamlit in background
streamlit run main.py --server.port=8501 --server.address=127.0.0.1 \
    --server.headless=true --browser.gatherUsageStats=false &
STREAMLIT_PID=$!

# Wait for Streamlit to be ready (with timeout + crash detection)
echo "Waiting for Streamlit to start..."
for i in $(seq 1 60); do
    if ! kill -0 "$STREAMLIT_PID" 2>/dev/null; then
        echo "Streamlit process died during startup" >&2
        exit 1
    fi
    if curl -s http://127.0.0.1:8501/_stcore/health > /dev/null 2>&1; then
        echo "Streamlit is up!"
        break
    fi
    sleep 1
done

# Start nginx in foreground
exec nginx -g "daemon off;"
