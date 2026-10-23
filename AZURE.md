# LuminaIQ on Azure

Workflow: `.github/workflows/azure.yml` (branch `jaisamyukth-changes`; `main` is not touched).

| Piece | Azure service | Notes |
|---|---|---|
| Backend API | **Container Apps** `luminaiq-api` (Central India) | Always on (min 1 replica, no cold starts), scales to 10 replicas at 40 concurrent requests each, 1 vCPU / 2 GiB per replica |
| Container images | **Container Registry** (Basic) | Images are built inside Azure (`az acr build`) |
| Website | **Static Web Apps** `luminaiq-web` (Free) | Served from a global CDN |
| AI | Foundry `Luminaiq` (East US) | GPT-5-mini, text-embedding-3-small, Document Intelligence |
| Database / auth | Supabase (unchanged) | |
| Search index | Qdrant Cloud (unchanged) | |

Rough monthly cost before free grants: Container Apps ≈ $15–60 depending on traffic, Registry ≈ $5, Static Web Apps free, AI pay-per-use (budget alert at $100).

## One-time setup (about 5 minutes)

### 1. Let GitHub deploy to your subscription

Azure portal → the **Cloud Shell** icon (top bar, `>_`) → **Bash**, then run:

```bash
az ad sp create-for-rbac --name luminaiq-github-deploy --role Contributor \
  --scopes /subscriptions/8fc489c7-8667-4694-922a-349586a44f9e --json-auth
```

Copy the whole JSON it prints. GitHub → Genrec-Community/LuminaIQ → Settings → Secrets and variables → Actions → **New repository secret**: name `AZURE_CREDENTIALS`, value the JSON.

### 2. Backend settings

Open `azure-deploy-secrets/BACKEND_ENV.txt` (sent to you separately, never committed). Replace the two `PASTE_FROM_RENDER` values with `QDRANT_URL` and `QDRANT_API_KEY` from Render → *luminaiq-backend-test* → Environment (or the *luminaiq-test-env* group). Add `RAZORPAY_*` lines if you use payments. Save the whole file as the secret `BACKEND_ENV`.

### 3. Deploy

GitHub → Actions → **Deploy to Azure** → **Run workflow** (branch `jaisamyukth-changes`). Later pushes deploy automatically. The run summary shows the API URL and the website address.

### 4. Point the apps at Azure

- **Android app:** Settings → Secrets and variables → Actions → **Variables** → `ANDROID_API_URL` = the API URL from the run summary (`https://luminaiq-api.….azurecontainerapps.io/api/v1`). The next Android build uses it.
- **Your domain (optional):** to serve `test.luminaiq.fun` (or `luminaiq.fun`) from Azure, Static Web App `luminaiq-web` → Custom domains → Add, then create the CNAME it shows in Cloudflare (DNS only, grey cloud). For a nicer API address, Container App `luminaiq-api` → Custom domains (e.g. `api.luminaiq.fun`), then set the variable `AZURE_API_URL`.
- **Supabase:** Authentication → URL Configuration → add the new website address (and custom domain) to Redirect URLs, so web Google sign-in returns there.

Once Azure is serving traffic, the Render and Vercel test services can be suspended.
