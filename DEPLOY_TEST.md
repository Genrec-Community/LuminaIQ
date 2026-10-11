# Deploying the test environment (test.luminaiq.fun)

Branch: `jaisamyukth-changes` · Production (`main`, luminaiq.fun) is not touched.

| Piece | Test | Production |
|---|---|---|
| Frontend | new Vercel project → `test.luminaiq.fun` | existing |
| Backend | new Render service `luminaiq-backend-test` | existing |
| Vector DB | **new** Qdrant Cloud cluster | existing |
| Database / auth | **shared** Supabase project | same |

Sharing Supabase means the same accounts, projects and books work on both.
The test backend rebuilds its own (empty) Qdrant automatically from the stored
book text the first time each project is opened — no re-uploads needed.

## 1. Qdrant (≈3 min)
1. https://cloud.qdrant.io → **Create cluster** → Free tier, any region close to your Render region.
2. Copy the **cluster URL** (`https://xxxx.cloud.qdrant.io:6333`) and create an **API key**.

## 2. Supabase (≈2 min)
1. SQL editor → run `backend/migrations/004_topic_outline.sql` (additive, safe for production).
2. Authentication → URL Configuration → **Redirect URLs** → add `https://test.luminaiq.fun/**`.

## 3. Render backend (≈10 min, mostly build time)
1. Environment Groups → open `luminaiq-env` → copy every variable into a new group named **`luminaiq-test-env`**, then change:
   - `QDRANT_URL` → new cluster URL
   - `QDRANT_API_KEY` → new key
   - `BACKEND_CORS_ORIGINS` (only if the group defines it) → add `https://test.luminaiq.fun`
2. **New + → Blueprint** → select this repo → Blueprint path **`render.test.yaml`** → Apply.
3. When it's live, open `https://luminaiq-backend-test.onrender.com/health` → should return `{"status":"healthy"}`.

## 4. Vercel frontend (≈5 min)
1. **Add New → Project** → import this repo.
   - Root directory: `frontend` · Framework: Vite
   - Production branch (Settings → Git): `jaisamyukth-changes`
2. Environment variables (see `frontend/.env.example`):
   - `VITE_MAIN_API_URL` = `https://luminaiq-backend-test.onrender.com/api/v1`
   - `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` = same as production
3. Deploy, then Settings → Domains → add **`test.luminaiq.fun`**.

## 5. DNS (≈2 min + propagation)
At your domain registrar / DNS host for `luminaiq.fun`, add the record Vercel shows, normally:

| Type | Name | Value |
|---|---|---|
| CNAME | `test` | `cname.vercel-dns.com` |

## Notes
- Render free tier sleeps after inactivity; the first request can take ~1 minute.
- Deleting a document on test removes it from the shared database (and so from production too).
- Re-embedding books into the new Qdrant uses your Azure embedding quota once per book.
