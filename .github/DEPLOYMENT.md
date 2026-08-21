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

Set Vercel's production `VITE_MAIN_API_URL` to the same App Service origin with
the `/api/v1` suffix. The backend deploy is stamped with `BUILD_SHA`; CI checks
that `/health` reports the expected commit before the frontend is released.
