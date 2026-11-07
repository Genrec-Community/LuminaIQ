# Moving Lumina IQ to another Azure account

Everything Lumina IQ runs on Azure can be re-created in a new account by the existing workflows; only the
database holds state, and `Azure ops → move-account` copies it exactly. Sign-in and files stay on Supabase,
so users, passwords and uploaded books don't move.

**Do it while the old account still runs.** A paused or expired subscription can't be copied from.

| Piece | How it moves |
| --- | --- |
| App database (`luminaiq-db`) | `Azure ops → move-account`: new server in the new account, exact copy, row counts compared |
| API (`luminaiq-api`) and image registry | `Deploy to Azure` builds them from scratch in the new account |
| Website (`luminaiq-web`) | `Deploy to Azure` creates it; then the domain is pointed at it |
| AI models (Foundry `Luminaiq`) | Not moved by any workflow: see step 6 |
| Sign-in, files | Stay on Supabase |

## 1. In the new account (the account owner)
1. Add the person running the move as **Owner** of the subscription (Subscription → Access control (IAM) → Add role
   assignment), so production doesn't depend on one person's login.
2. Create the deploy identity and copy the JSON it prints:
   ```bash
   az ad sp create-for-rbac --name luminaiq-github-deploy --role Contributor \
     --scopes /subscriptions/<NEW-SUBSCRIPTION-ID> --json-auth
   ```
3. GitHub → Genrec-Community/LuminaIQ → Settings → Secrets and variables → Actions → New repository secret:
   **`NEW_AZURE_CREDENTIALS`** = that JSON. Leave `AZURE_CREDENTIALS` (the old account) as it is for now.
   Never paste the JSON into a chat.

## 2. Check (dry run, changes nothing)
Actions → **Azure ops** → Run workflow → task **`move-account`**, dry_run **on**. It signs in to both accounts and
prints the old database's tables and row counts, and what will be created in the new one.

Optional first: run task **`inspect`** with `AZURE_CREDENTIALS` temporarily set to the new account to see which
regions and sizes it may use. Pass them as `location` / `sku` below; a paid account normally allows Central India.

## 3. Move (about 15 minutes of downtime, during a quiet hour)
1. Azure ops → `move-account`, dry_run **off** (stop_old_api on, overwrite_target off; `location` e.g. `centralindia`).
   It stops the old API taking requests, creates the database in the new account, copies everything
   (`pg_dump`/`pg_restore`, including the job queue and migration history) and compares every table's row count.
   If anything fails, it switches the old API back on and nothing else has changed.
2. Replace the secret **`AZURE_CREDENTIALS`** with the new account's JSON (the same value as
   `NEW_AZURE_CREDENTIALS`).
3. Actions → **Deploy to Azure** → Run workflow (branch `main`). It builds the API image, puts it into the app that
   step 1 prepared (with `DATABASE_URL` already set), and builds and publishes the website against the new API.
   It ends by checking `/health`.
4. Point the domain: Static Web App `luminaiq-web` (new account) → Custom domains → add `luminaiq.fun`, and update
   the CNAME at the DNS provider (Cloudflare: DNS only). If the API has a custom domain (`AZURE_API_URL`), add it on
   the new Container App and update its CNAME too.
5. Supabase → Authentication → URL Configuration: add the new website address to Redirect URLs (Google sign-in).
6. Check `/ready` on the new API, sign in, open a book, chat, a quiz, a school dashboard, a paid account.

## 4. After the move
- **AI models:** `BACKEND_ENV` still points at the old account's Foundry resource (`LLM_*`, `LLM_DEEP_*`,
  `EMBEDDING_*`), so answers stop when the old account is paused. Before that, either deploy the same models in the
  new account's Foundry (model access requests can take a day) or switch to another OpenAI-compatible provider;
  then update those lines in `BACKEND_ENV` and redeploy. Keep the same embedding model, or book search has to be
  rebuilt (re-index every book).
- Delete `NEW_AZURE_CREDENTIALS`.
- Keep the old account untouched for a few days as the fallback (re-enable its ingress and point DNS back), then
  delete its resource group.
- Android builds use `ANDROID_API_URL`; update it if the API address changed, and ship a new build.

## If the move must be abandoned
The old database is never modified. If the old API was stopped, switch it back on:
```bash
az containerapp ingress enable -n luminaiq-api -g luminaiq --type external --target-port 8000
```
