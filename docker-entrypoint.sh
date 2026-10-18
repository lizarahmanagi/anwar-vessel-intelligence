#!/bin/sh
set -e

mkdir -p /app/logs /app/reports /app/weekly_data

# Materialise container env vars into /app/.env so cron children (which get a
# minimal environment) can load them via python-dotenv.
env | grep -E '^(GROQ_|SENDER_|SMTP_|RECEIVER_)' > /app/.env || true

echo "[osiris] cron starting - daily pipeline 10:30 AM Asia/Dhaka (single daily email)"
exec cron -f
