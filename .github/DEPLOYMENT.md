# CI/CD Configuration

Pull requests and pushes run backend regression tests, the Topic Graph
orchestration benchmark, frontend linting, and the production frontend build.
The benchmark JSON is retained as a workflow artifact for 30 days.

Pushes to `main` deploy the exact commit after every CI job passes.

## Production Environment

Create a protected GitHub Environment named `production`. Configure these
environment variables:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_WEBAPP_NAME`, currently `luminaiq-api-v2`
- `AZURE_RESOURCE_GROUP`
- `BACKEND_API_URL`, without `/api/v1`, for example
  `https://luminaiq-api-v2.azurewebsites.net`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`

Configure one environment secret:

- `VERCEL_TOKEN`

The Azure identity uses GitHub OIDC rather than a stored Azure password. Give
it permission to deploy and configure the target App Service, then add a
federated credential scoped to this repository's `production` environment.
Runtime Supabase, Qdrant, OCR, and model credentials remain on App Service and
the Vercel project; they are not copied into CI.

Apply reviewed Supabase migrations before merging application code that uses
them. In particular, `backend/migrations/004_atomic_topic_graph.sql` and
`006_ordered_topic_graph_publication.sql` must be installed in order before
Graph Build replacement is enabled. The backend fails closed rather than
deleting an active graph when either RPC migration is missing.
Migration 006 intentionally retains the migration-004 two-argument RPC during
rolling deployment; remove that legacy overload only after old instances drain.
Deploy the migration-007 fail-closed application first, wait for all previous
instances to drain, and only then apply migration 007. This avoids mixed workers
publishing through incompatible fingerprint protocols.

Set Vercel's production `VITE_MAIN_API_URL` to the same App Service origin with
the `/api/v1` suffix. CI embeds the commit in `build_info.py` inside the ZIP and
checks that `/health` reports that immutable artifact value before releasing
the frontend. Remote Oryx build is enabled so `requirements.txt` is installed.
