FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Dhaka

RUN apt-get update && apt-get install -y --no-install-recommends cron tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/share/zoneinfo/Asia/Dhaka /etc/localtime \
    && echo "Asia/Dhaka" > /etc/timezone

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs /app/reports /app/weekly_data \
    && chmod +x /app/docker-entrypoint.sh \
    && printf 'SHELL=/bin/sh\nPATH=/usr/local/bin:/usr/bin:/bin\n\n30 10 * * * root cd /app && /usr/local/bin/python daily_analysis.py 2>&1 | tee -a /app/logs/daily_cron.log > /proc/1/fd/1\n' > /etc/cron.d/osiris \
    && chmod 0644 /etc/cron.d/osiris

ENTRYPOINT ["/app/docker-entrypoint.sh"]
