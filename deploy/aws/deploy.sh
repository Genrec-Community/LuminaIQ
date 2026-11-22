#!/usr/bin/env bash
# Runs on the server (via SSM from the "Deploy to AWS" workflow).
#   deploy.sh <api-image>     pull the image, refresh settings and website, restart what changed
set -euo pipefail
IMAGE="${1:?image}"
BUCKET=luminaiq-backups-524554316555
WEB=luminaiq-web-524554316555
REGION=ap-southeast-2
cd /opt/luminaiq
export AWS_DEFAULT_REGION=$REGION

aws s3 cp "s3://$BUCKET/deploy/docker-compose.yml" docker-compose.yml --only-show-errors
aws s3 cp "s3://$BUCKET/deploy/Caddyfile" Caddyfile --only-show-errors
aws s3 cp "s3://$BUCKET/deploy/backup.sh" backup.sh --only-show-errors && chmod +x backup.sh

# Settings: the old Azure BACKEND_ENV, then secrets from SSM, then AWS overrides (later keys win;
# "@NAME" in an override takes the value of NAME, e.g. a secret from SSM)
umask 077
aws s3 cp "s3://$BUCKET/config/backend_env" /tmp/base.env --only-show-errors
aws s3 cp "s3://$BUCKET/deploy/backend.aws.env" /tmp/over.env --only-show-errors
: > /tmp/ssm.env
for name in $(aws ssm get-parameters-by-path --path /luminaiq/env/ --query "Parameters[].Name" --output text 2>/dev/null || true); do
  val=$(aws ssm get-parameter --name "$name" --with-decryption --query Parameter.Value --output text)
  echo "${name##*/}=$val" >> /tmp/ssm.env
done
source /opt/luminaiq/pg.env
echo "DATABASE_URL=postgresql://lumina:${POSTGRES_PASSWORD}@postgres:5432/lumina" >> /tmp/ssm.env
python3 - /tmp/base.env /tmp/ssm.env /tmp/over.env > backend.env.new <<'PY'
import sys
env = {}
for path in sys.argv[1:]:
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\r\n")
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v[1:-1] if len(v) >= 2 and v[0] == v[-1] == '"' else v
        if v == "__REMOVE__":
            env.pop(k, None)
        else:
            env[k] = v
# "@NAME" copies another key's value (one AI key serving chat, deep model and embeddings)
for k, v in list(env.items()):
    if v.startswith("@") and v[1:] in env:
        env[k] = env[v[1:]]
for k, v in env.items():
    print(f"{k}={v}")
PY
mv backend.env.new backend.env
rm -f /tmp/base.env /tmp/over.env /tmp/ssm.env
# Names Caddy serves (and gets HTTPS certificates for)
aws s3 cp "s3://$BUCKET/deploy/site-hosts" /tmp/site-hosts --only-show-errors
echo "SITE_HOSTS=$(head -1 /tmp/site-hosts)" > site.env

# Website
mkdir -p web
aws s3 sync "s3://$WEB/" web/ --delete --only-show-errors

# Images
aws ecr get-login-password | docker login --username AWS --password-stdin "${IMAGE%%/*}" >/dev/null
docker pull -q "$IMAGE" >/dev/null
export API_IMAGE="$IMAGE"
echo "API_IMAGE=$IMAGE" > .env
docker compose up -d --remove-orphans
docker compose restart caddy >/dev/null 2>&1 || true

for i in $(seq 1 40); do
  code=$(docker compose exec -T api curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || true)
  [ "$code" = "200" ] && { echo "API healthy"; break; }
  sleep 5
done
docker compose ps
docker image prune -af --filter "until=72h" >/dev/null 2>&1 || true
[ "${code:-}" = "200" ] || { docker compose logs --tail 80 api; exit 1; }
