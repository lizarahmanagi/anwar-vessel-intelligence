#!/bin/sh
set -e

mkdir -p /app/logs /app/reports /app/weekly_data

# Materialise container env vars into /app/.env so cron children (which get a
# minimal environment) can load them via python-dotenv.
env | grep -E '^(GROQ_|SENDER_|SMTP_|RECEIVER_)' > /app/.env || true

echo "[osiris] cron starting — daily pipeline 10:05 AM Asia/Dhaka (weekly Sunday 10:20 AM)"
exec cron -f
