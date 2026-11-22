#!/usr/bin/env bash
# Nightly database backup to S3 (cron on the server). Keeps the last 14 in S3 via lifecycle rule.
set -euo pipefail
cd /opt/luminaiq
TS=$(date -u +%Y%m%dT%H%M%SZ)
docker compose exec -T postgres pg_dump -U lumina -d lumina -Fc > /tmp/lumina.dump
aws s3 cp /tmp/lumina.dump "s3://luminaiq-backups-524554316555/nightly/lumina-$TS.dump" --sse AES256 --only-show-errors --region ap-southeast-2
rm -f /tmp/lumina.dump
