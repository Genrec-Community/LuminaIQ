#!/bin/bash
# First boot of the Lumina IQ server (Amazon Linux 2023). The app itself arrives with deploy.sh.
set -euxo pipefail
dnf install -y docker cronie python3
systemctl enable --now docker crond
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/download/v2.39.4/docker-compose-linux-x86_64" -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
# 4 GB swap: OCR of big books needs headroom on a 2 GB machine
if [ ! -f /swapfile ]; then
  dd if=/dev/zero of=/swapfile bs=1M count=4096; chmod 600 /swapfile; mkswap /swapfile; swapon /swapfile
  echo "/swapfile swap swap defaults 0 0" >> /etc/fstab
fi
sysctl -w vm.swappiness=10; echo "vm.swappiness=10" > /etc/sysctl.d/90-swap.conf
mkdir -p /opt/luminaiq/{pgdata,web,caddy-data,caddy-config}
umask 077
[ -f /opt/luminaiq/pg.env ] || printf 'POSTGRES_USER=lumina\nPOSTGRES_DB=lumina\nPOSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 24)" > /opt/luminaiq/pg.env
echo "15 20 * * * root /opt/luminaiq/backup.sh >> /var/log/luminaiq-backup.log 2>&1" > /etc/cron.d/luminaiq-backup
