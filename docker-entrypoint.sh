#!/bin/sh
set -e

mkdir -p /app/logs /app/reports /app/weekly_data

# Materialise container env vars into /app/.env so cron children (which get a
# minimal environment) can load them via python-dotenv.
env | grep -E '^(GROQ_|SENDER_|SMTP_|RECEIVER_)' > /app/.env || true

# Run the daily pipeline once at container start if today's report does not
# exist yet (validates the full chain on deploy; cron takes over after that).
TODAY_MD="vessel_analysis_$(date +%d_%m_%Y).md"
if [ ! -f "/app/reports/$TODAY_MD" ]; then
    echo "[osiris] No report for today - running pipeline now..."
    cd /app && timeout 600 python daily_analysis.py >> /app/logs/startup_run.log 2>&1 || true
else
    echo "[osiris] Report for today already exists - skipping startup run."
fi

echo "[osiris] cron starting - daily pipeline 10:05 AM Asia/Dhaka (weekly Sunday 10:20 AM)"
exec cron -f
