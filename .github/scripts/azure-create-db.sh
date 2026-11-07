#!/usr/bin/env bash
# Creates (or finds) the app database in the Azure subscription the CLI is signed in to, and keeps its
# connection string as the "database-url" secret on the API Container App. Used by Azure ops →
# create-db and → move-account. Safe to re-run: existing pieces are left as they are.
#
# Env: RG, LOCATION, APP, ENVIRONMENT, PG, PG_DB, PG_ADMIN; optional LOCS / SKUS (space-separated
# regions / sizes to try; `inspect` lists which ones the subscription may use).
set -euo pipefail

az extension add --name containerapp --upgrade --only-show-errors
for p in Microsoft.DBforPostgreSQL Microsoft.App Microsoft.OperationalInsights; do
  az provider register --namespace "$p" --wait --only-show-errors >/dev/null
done
az group show -n "$RG" >/dev/null 2>&1 || az group create -n "$RG" -l "$LOCATION" -o none

# A fresh subscription has no API app yet, but the connection string must live on it (the deploy
# reads it from there). Create the environment and a placeholder app; the next deploy replaces the
# image and sets the real port, registry and settings.
if ! az containerapp show -n "$APP" -g "$RG" >/dev/null 2>&1; then
  az containerapp env show -n "$ENVIRONMENT" -g "$RG" >/dev/null 2>&1 || \
    az containerapp env create -n "$ENVIRONMENT" -g "$RG" -l "$LOCATION" -o none
  az containerapp create -n "$APP" -g "$RG" --environment "$ENVIRONMENT" \
    --image mcr.microsoft.com/k8se/quickstart:latest --target-port 80 --ingress external \
    --min-replicas 0 --max-replicas 1 -o none
  echo "Created a placeholder $APP (the next deploy puts the real API in it)"
fi

state() {
  # ARM keeps a failed server's name (and region) until it is fully deleted, so ask ARM too
  local s; s=$(az postgres flexible-server list -g "$RG" --query "[?name=='$PG'].state | [0]" -o tsv 2>/dev/null || true)
  [ -n "$s" ] || { az resource list -g "$RG" -n "$PG" --resource-type Microsoft.DBforPostgreSQL/flexibleServers --query "[0].name" -o tsv 2>/dev/null | grep -q . && s=Dropping; }
  echo "$s"
}
# A failed create leaves a half-made server that Azure deletes on its own ("Dropping");
# wait for that to finish instead of mistaking it for a working server.
for _ in $(seq 1 60); do
  s=$(state); [ "$s" = "Dropping" ] || break
  echo "Waiting for a failed earlier attempt to be removed..."; sleep 20
done
s=$(state)
[ "$s" != "Dropping" ] || { echo "::error::$PG is still being removed by Azure; run again in a few minutes"; exit 1; }
echo "Existing server state: ${s:-none}"

if [ -z "$s" ]; then
  PASS="$(openssl rand -base64 36 | tr -dc 'A-Za-z0-9' | head -c 32)Aa1"
  echo "::add-mask::$PASS"
  # Burstable B1ms is plenty for today's data (resize later without moving data). Free-credit
  # subscriptions can't create every size in every region (SkuNotAvailable), so try the given
  # regions and sizes in order. Public access is limited by firewall to Azure services.
  created=""
  for loc in ${LOCS:-$LOCATION southeastasia}; do
    for sku in ${SKUS:-Standard_B1ms Standard_B2s}; do
      case "$sku" in Standard_B*) tier=Burstable ;; Standard_E*) tier=MemoryOptimized ;; *) tier=GeneralPurpose ;; esac
      echo "Trying $sku ($tier) in $loc"
      if az postgres flexible-server create -n "$PG" -g "$RG" -l "$loc" \
           --version 16 --tier "$tier" --sku-name "$sku" --storage-size 32 \
           --admin-user "$PG_ADMIN" --admin-password "$PASS" \
           --public-access 0.0.0.0 --backup-retention 7 --yes -o none; then
        created="$sku in $loc"; break 2
      fi
      for _ in $(seq 1 45); do [ -z "$(state)" ] && break; echo "Waiting for Azure to remove the failed attempt..."; sleep 20; done
    done
  done
  [ -n "$created" ] || { echo "::error::No Postgres size could be created in any tried region"; exit 1; }
  echo "Created $created"
  URL="postgresql://$PG_ADMIN:$PASS@$PG.postgres.database.azure.com:5432/$PG_DB?sslmode=require"
  echo "::add-mask::$URL"
  # The Container App holds the connection string; nothing reads it until DATABASE_URL points at it.
  az containerapp secret set -n "$APP" -g "$RG" --secrets "database-url=$URL" -o none
fi

# pgvector and uuid-ossp must be allow-listed on Azure before CREATE EXTENSION works
az postgres flexible-server parameter set -g "$RG" -s "$PG" --name azure.extensions --value "VECTOR,UUID-OSSP" -o none
az postgres flexible-server db show -g "$RG" -s "$PG" -n "$PG_DB" >/dev/null 2>&1 || \
  az postgres flexible-server db create -g "$RG" -s "$PG" -n "$PG_DB" -o none
az postgres flexible-server show -n "$PG" -g "$RG" --query "{name:name, state:state, version:version, sku:sku.name, host:fullyQualifiedDomainName}" -o table
