# Moving the app data from Supabase to Azure Database for PostgreSQL

Owner decisions: production stays on **Azure** (2026-11-06), and the live data moves with it (2026-11-05).
This step moves the **database** only. Sign-in and file storage (PDFs, extracted book text, chat photos) stay on
Supabase for now, so nobody re-registers and every file path keeps working.

## Before and after

| | Today (`main`) | After the switch (`production-grade`) |
|---|---|---|
| API | Container App `luminaiq-api` | Same app, new image (web + background worker in each replica) |
| Website | Static Web App `luminaiq-web` | Same, new build |
| App data | Supabase Postgres | **Azure Database for PostgreSQL 16 `luminaiq-db`** (pgvector), Southeast Asia (see below) |
| Book search | Qdrant | pgvector in the same database, rebuilt from the stored text |
| AI models | Azure Foundry, `LLM_*` / `LLM_DEEP_*` / `EMBEDDING_*` | Same keys: `LLM_*` is read as the small model, `LLM_DEEP_*` is mapped to `BIG_LLM_*` by `azure.yml` |
| Sign-in, files | Supabase | Supabase (unchanged in this step) |

The API address stays the same, so the website, the Android app (`ANDROID_API_URL`) and Razorpay webhooks need no change.

Live data on 2026-11-04: 156 accounts, 61 users with 208 books and 265 documents, 379 chat messages, 4 paid/unlimited
plans, 3 schools, 3 payments. The largest table, `topic_relations`, has ~7,000 rows; the copy takes a minute or two.

## Subscription

The subscription runs on free credits. Azure pauses a free-trial subscription when its credits run out or expire,
which would take luminaiq.fun offline. **Upgrade it to pay-as-you-go before the credits expire** (Azure portal →
Subscriptions → Upgrade); unused credits carry over and nothing that runs changes.

## Region

The server is in **Southeast Asia**, not Central India next to the API: on this free-credit subscription Central India
refused both Burstable sizes (`SkuNotAvailable`), and South India, East US/US 2, West US 2 and West Europe are closed to
it (`inspect` lists this per region). Every query crosses India ↔ Singapore, so expect a few tens of milliseconds more
per query. To move it next to the API later: upgrade the subscription (or open a support request, issue type
"Service and subscription limits", for Burstable in Central India), run `create-db` with `location=centralindia` under a
new server name, and re-run `migrate` into it.

## What the migration does (`backend/scripts/migrate_from_supabase.py`)

- Creates the new schema on the target (`db/schema/*`), then copies every table the two databases share, parents
  before children, in batches. Re-running it adds nothing (`ON CONFLICT DO NOTHING`).
- `auth.users` → `app_users` (id, email), so plans, unlimited access and analytics keep working.
- Converts the columns whose types changed:
  - `mcq_tests.questions`, `subjective_tests.questions/results`, `answer_evaluations.ai_feedback`: live rows hold a
    JSON *string* inside jsonb; it's unwrapped to the text the app `json.loads()`.
  - `text[]` → jsonb array (`completed_topics`, `topics_visited`, exam topics); exam timestamps → date (India).
- A null in a column the new schema requires takes that column's default (the row isn't lost).
- Rows whose parent is gone (e.g. messages of a deleted book) are skipped and counted.
- Leaves behind 7 columns nothing reads any more (listed in the dry run) and `document_chunks` (empty).
- Puts old chats into one "Earlier chat" per book and backfills `user_active_days`.
- Queues a `reindex_document` job per completed document; the worker rebuilds its passages from the stored text in
  Supabase Storage (embedding cost: about ₹0.35 per book). Until a book is re-indexed, search falls back to its stored
  text, so it keeps working.
- Book Store books are copied as they are. All 7 were unlisted on 2026-11-04 (`is_public = false`).

Known limit: books uploaded before this branch were extracted without page breaks, so their citations have no page
numbers. Re-uploading a book gives page-accurate citations.

Tested in `backend/tests/test_migrate_from_supabase.py` and rehearsed against a copy of the live table definitions.

## Steps (GitHub → Actions → **Azure ops** → Run workflow)

1. **`create-db`** (done 2026-11-06): creates `luminaiq-db` (Burstable B1ms, 32 GB, 7-day backups, firewall: Azure
   services only; region and size are inputs), allow-lists `VECTOR` and `UUID-OSSP`, creates the `lumina` database, and stores its connection string
   as the `database-url` secret on `luminaiq-api`. Nothing reads it until the new code is deployed.
2. **Supabase connection string** as a repository secret: Supabase → Project Settings → Database → Connection string →
   **Session pooler**; add `?sslmode=require` and your database password. GitHub → Settings → Secrets and variables →
   Actions → New repository secret `SUPABASE_DB_URL`.
3. **`migrate` with dry run** (default): prints the plan and row counts, copies nothing.
4. **Switch-over** (about 10 minutes, during a quiet hour):
   1. `migrate` with dry run **off**: copies the data. It must end with `Done.`
   2. Merge `production-grade` into `main`: `Deploy to Azure` builds the new image and website and points
      `DATABASE_URL` at `luminaiq-db`. The app applies any newer schema files on start.
   3. Run `migrate` (dry run off) once more: it adds rows written by the old API during the deploy. Rows the old API
      *changed* in those minutes keep their earlier copy, so keep the window short.
   4. Check: `/health` and `/ready` on the API, sign in, open a book, chat, quiz, a school dashboard, a paid account,
      and the re-index jobs finishing (admin → Analytics → Health).
5. Keep the Supabase database untouched for 30 days as the fallback (rolling back = redeploying the previous image).

`main` deploys with `.github/workflows/azure.yml`, which now refuses to deploy if the `database-url` secret is missing,
so the new code can't start against nothing.

## Later
- Files off Supabase Storage (PDFs, book text, chat photos), then sign-in (owner decision 2).
- The `documents` storage bucket (original PDFs) is public today: anyone with a file's link can download it. Make it
  private and serve signed links.
