#!/bin/sh
# گواهی خودامضا فقط برای آزمایش استقرار (مرورگر هشدار می‌دهد). برای production از Let's Encrypt استفاده کنید.
set -eu
mkdir -p deploy/certs
openssl req -x509 -nodes -newkey rsa:2048 -days 30 -subj "/CN=${1:-localhost}" \
    -keyout deploy/certs/privkey.pem -out deploy/certs/fullchain.pem
echo "deploy/certs/ ساخته شد."
