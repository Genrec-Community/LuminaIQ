# Test environment — test.luminaiq.fun

Branch: **`jaisamyukth-changes`** · Production (`main`, luminaiq.fun) is not touched.

## Status

| Piece | Resource | Status |
|---|---|---|
| Database / auth | Supabase project **Lumina IQ** (`bcosfvilvwyxtrctsmez`, ap-south-1) — **shared with production** | ✅ migration `004_topic_outline` applied |
| Frontend | Vercel project **`luminaiq-test`** (`prj_QdOOgYdPFsppjAWfn5AFcqTDQQWL`) | ✅ created, deployed, domain attached |
| Domain | `test.luminaiq.fun` → Vercel | ✅ resolving (Cloudflare CNAME) |
| Supabase auth redirect | `https://test.luminaiq.fun/**` | ⏳ dashboard-only setting (step 2) |
| Vector DB | new Qdrant Cloud cluster | ⚠️ should be set on the Render service (`QDRANT_URL`, `QDRANT_API_KEY`) — not verified by Claude |
| Backend | Render service **`luminaiq-backend-test`** (`srv-db5p2k2jnfac73b8hpcg`), workspace *Jai Samyukth*, project *Luminaiq-test*, Singapore, free plan, Docker, root `backend/`, branch `jaisamyukth-changes` | ✅ live at https://luminaiq-backend-test.onrender.com |

Production for comparison: Vercel project `lumina-iq` (luminaiq.fun, www.luminaiq.fun) and Render
service `luminaiq-backend`. Neither was modified.

## What is already configured

### Vercel — `luminaiq-test`
- Git: `Genrec-Community/LuminaIQ`, root directory `frontend`, framework Vite.
- Domain `test.luminaiq.fun` is bound to branch `jaisamyukth-changes`
  (every push to that branch redeploys the test site).
- Ignored build step: builds **only** run for `jaisamyukth-changes`; pushes to `main` are skipped
  so the test project never mirrors production.
- Environment variables (all environments):

  | Key | Value |
  |---|---|
  | `VITE_MAIN_API_URL` | `https://luminaiq-backend-test.onrender.com/api/v1` |
  | `VITE_SUPABASE_URL` | `https://bcosfvilvwyxtrctsmez.supabase.co` |
  | `VITE_SUPABASE_ANON_KEY` | Supabase legacy anon key (public, same as production) |

  If Render gives the backend a different URL in step 4, update `VITE_MAIN_API_URL` in
  Vercel → luminaiq-test → Settings → Environment Variables, then redeploy.
- Deployment URL (Vercel login required because of deployment protection):
  `luminaiq-test.vercel.app`. The custom domain is public.

### Render — `luminaiq-backend-test`
- Created manually in the dashboard (equivalent to `render.test.yaml`), auto-deploys on every push
  to `jaisamyukth-changes`.
- `BACKEND_CORS_ORIGINS` = `https://test.luminaiq.fun,https://luminaiq-test.vercel.app,http://localhost:5173`
- Must carry the same Supabase / Azure OpenAI / `SECRET_KEY` variables as production
  (`luminaiq-backend`, workspace *My Workspace*), with its own `QDRANT_URL` / `QDRANT_API_KEY`.
- Health check: `GET /health` → `{"status":"healthy","service":"lumina-backend"}`.

### AI providers (all OpenAI-compatible)
The backend picks providers from env vars — any OpenAI-compatible API works:

| Purpose | Switch | Settings |
|---|---|---|
| Chat / topics / quizzes | `LLM_PROVIDER` = `auto` \| `azure` \| `openai` | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, optional `LLM_REASONING_EFFORT` |
| Book search (embeddings) | `EMBEDDING_PROVIDER` = `auto` \| `azure` \| `openai` | `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION` |

`auto` = Azure OpenAI when `AZURE_OPENAI_*` is set, otherwise the OpenAI-compatible settings.

Test service currently: `LLM_PROVIDER=openai`, `LLM_BASE_URL=https://api.inceptionlabs.ai/v1`,
`LLM_MODEL=mercury-2.5`, `LLM_REASONING_EFFORT=low` (key stored only in Render).
Mercury has no embeddings API, so embeddings still need Azure (`AZURE_OPENAI_*` with
`EMBEDDING_MODEL=text-embedding-3-small`, `EMBEDDING_DIMENSION=1536`) or another
OpenAI-compatible embeddings provider with `EMBEDDING_PROVIDER=openai`.

### Vercel deployment protection
Turned **off** for `luminaiq-test` (Vercel Authentication was redirecting `test.luminaiq.fun`
assets such as `site.webmanifest` to `vercel.com/sso-api`, which blocks every visitor not logged in
to Vercel). The preview toolbar is disabled too. Production project settings are unchanged.

### Supabase — `Lumina IQ`
Applied `backend/migrations/004_topic_outline.sql` as migration `004_topic_outline`:
- `documents.topic_outline JSONB DEFAULT '[]'` (+ column comment)
- `idx_documents_project_status_created (project_id, upload_status, created_at)`
- `idx_topic_relations_project_type (project_id, relation_type)`

Additive only — production keeps working and simply ignores the new column.

## Remaining steps (need your logins)

### 1. Cloudflare DNS (≈2 min)
`luminaiq.fun` uses Cloudflare nameservers. In Cloudflare → luminaiq.fun → DNS → **Add record**:

| Type | Name | Target | Proxy status |
|---|---|---|---|
| CNAME | `test` | `cname.vercel-dns.com` | **DNS only** (grey cloud) |

Vercel issues the HTTPS certificate automatically once the record resolves (usually minutes).

### 2. Supabase auth redirect (≈1 min)
Supabase → Lumina IQ → Authentication → URL Configuration → **Redirect URLs** → add
`https://test.luminaiq.fun/**`. Without this, Google sign-in on the test site redirects to production.

### 3. Qdrant (≈3 min)
https://cloud.qdrant.io → **Create cluster** (free tier, region near Render). Copy the cluster URL
(`https://xxxx.cloud.qdrant.io:6333`) and create an API key.

### 4. Render backend (≈10 min, mostly build time)
1. Environment Groups → open `luminaiq-env` → copy every variable into a new group
   **`luminaiq-test-env`**, then change:
   - `QDRANT_URL` / `QDRANT_API_KEY` → the new cluster
   - `BACKEND_CORS_ORIGINS` (only if the group defines it) → add `https://test.luminaiq.fun`
2. **New + → Blueprint** → this repo → Blueprint path **`render.test.yaml`** → Apply.
3. Check `https://luminaiq-backend-test.onrender.com/health` returns `{"status":"healthy"}`.

The new Qdrant starts empty: the first time a project is opened on the test site the backend
re-embeds its books from the stored text automatically (no re-uploads).

## Things to know (shared database)
- Accounts, projects and books are the same on test and production.
- **Deleting a document on test deletes it in production too.**
- Re-embedding into the new Qdrant uses Azure embedding quota once per book.
- The test backend never changes a document's processing status, so production users never see
  their books flip to "processing"/"failed" because of the test environment.
- Render free tier sleeps after inactivity; the first request can take ~1 minute.

## Supabase advisor notes (pre-existing, not caused by these changes)
- Security: `increment_xp` has a mutable `search_path`; `vector` extension lives in `public`;
  leaked-password protection is off (Authentication → Policies).
- Performance: many RLS policies re-evaluate `auth.uid()` per row (`auth_rls_initplan`), multiple
  permissive policies per table, and 19 duplicate indexes. Worth a cleanup pass later.
