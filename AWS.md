# Lumina IQ on AWS

Since 2026-11-22 production runs on AWS account `524554316555`, region **ap-southeast-2 (Sydney)**, the only
region the account's organisation allows. The Azure subscription was disabled (read-only) after its credit ran out.

| Piece | Where | Notes |
|---|---|---|
| Server | EC2 `luminaiq-server` (t3.small, 2 vCPU, 2 GB + 4 GB swap, 30 GB disk), Elastic IP `3.105.245.239` | No SSH: use SSM (Session Manager) or `AWS ops` |
| API | Docker container `api` on the server | Image from ECR `luminaiq-backend`, background jobs run inside it |
| Database | Docker container `postgres` (pgvector, Postgres 16) on the server, data in `/opt/luminaiq/pgdata` | Nightly `pg_dump` to `s3://luminaiq-backups-524554316555/nightly/` (01:45 IST, kept 14 days) |
| Website + HTTPS | Docker container `caddy`: serves the built site from S3 `luminaiq-web-524554316555`, sends `/api/*` to the API, gets certificates itself | Names it answers for: `deploy/aws/site-hosts` |
| Sign-in, files | Supabase `bcosfvilvwyxtrctsmez` (unchanged) | |
| Settings | Old Azure `BACKEND_ENV` copied to `s3://luminaiq-backups-524554316555/config/backend_env`, overrides in `deploy/aws/backend.aws.env`, secrets in SSM Parameter Store `/luminaiq/env/<NAME>` | Later keys win; `__REMOVE__` drops a key |

Cost from the $100 AWS credit: about $19/month server + $3 disk + $3.60 IP + a few cents of S3 ≈ **$26/month**. AI is billed by
whichever provider `LLM_*` / `EMBEDDING_*` point at.

## Deploys
`Deploy to AWS` (`.github/workflows/aws.yml`) runs on every push to `main` that touches the app: builds the API image, builds
the website with the API at `/api/v1` (same origin), uploads both, then runs `deploy/aws/deploy.sh` on the server through
SSM. GitHub signs in to AWS with OIDC (IAM role `luminaiq-github-deploy`); no AWS keys are stored in GitHub.

## Operations
`AWS ops` (`.github/workflows/aws-ops.yml`): `status`, `migrate-supabase`, `reindex`, `backup`.

## Changing a secret
AWS console → Systems Manager → Parameter Store → create `/luminaiq/env/<NAME>` (SecureString), then re-run
`Deploy to AWS`. Example: `/luminaiq/env/LLM_API_KEY`.

## Domain
Cloudflare DNS for `luminaiq.fun`: `A luminaiq.fun → 3.105.245.239` and `A www → 3.105.245.239`, **DNS only** (grey cloud),
(the names are already in `deploy/aws/site-hosts`, so HTTPS starts by itself). The Android app uses `https://luminaiq.fun/api/v1`
(`AWS_ANDROID_API_URL` overrides it).
