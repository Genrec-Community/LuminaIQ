# Moving Lumina IQ to AWS

Owner decision (2026-11-05): the software runs on AWS only, and the live data moves from Supabase
to AWS. This first step moves the **database**. Sign-in and file storage (PDFs, extracted book text,
chat photos) stay on Supabase for now, so nobody re-registers and every file path keeps working.

## What exists today

| | Today (`main`) | After the move (`production-grade`) |
|---|---|---|
| API | Azure Container App `luminaiq-api` | AWS: one Docker image, `web` + `worker` (see `AGENTS.md` §4) |
| Website | Azure Static Web App `luminaiq-web` | AWS (S3 + CloudFront, or Amplify) |
| App data | Supabase Postgres | **RDS PostgreSQL 16 with pgvector** |
| Book search | Qdrant | pgvector in the same RDS (rebuilt from stored text) |
| Sign-in, files | Supabase | Supabase (unchanged in this step) |

Live data on 2026-11-04: 156 accounts, 61 users with 208 books and 265 documents, 379 chat
messages, 4 paid/unlimited plans, 3 schools, 3 payments. The largest table, `topic_relations`, has
~7,000 rows, so the copy itself takes a minute or two.

## What the migration does (`backend/scripts/migrate_from_supabase.py`)

- Creates the new schema on the target (`db/schema/*`), then copies every table the two databases
  share, parents before children, in batches. Re-running it adds nothing (`ON CONFLICT DO NOTHING`).
- `auth.users` → `app_users` (id, email), so plans, unlimited access and analytics keep working.
- Converts the columns whose types changed:
  - `mcq_tests.questions`, `subjective_tests.questions/results`, `answer_evaluations.ai_feedback`:
    live rows hold a JSON *string* inside jsonb; it's unwrapped to the text the app `json.loads()`.
  - `text[]` → jsonb array (`completed_topics`, `topics_visited`, exam topics); exam timestamps → date (India).
- A null in a column the new schema requires takes that column's default (the row isn't lost).
- Rows whose parent is gone (e.g. messages of a deleted book) are skipped and counted.
- Leaves behind 7 columns nothing reads any more (listed in the dry run) and `document_chunks` (empty).
- Puts old chats into one "Earlier chat" per book and backfills `user_active_days`.
- Queues a `reindex_document` job per completed document; the worker rebuilds its passages from the
  stored text in Supabase Storage (embedding cost: about ₹0.35 per book). Until a book is re-indexed,
  search falls back to its stored text, so it keeps working.
- Book Store books are copied as they are. All 7 were unlisted on 2026-11-04 (`is_public = false`).

Known limit: books uploaded before this branch were extracted without page breaks, so their
citations have no page numbers. Re-uploading a book gives page-accurate citations.

Tested in `backend/tests/test_migrate_from_supabase.py` and rehearsed against a copy of the live
table definitions.

## Steps

### 1. AWS resources (Mumbai, `ap-south-1`, next to Supabase and the users)
1. **RDS for PostgreSQL 16** (pgvector is built in). Private subnets, a security group that only the
   API servers can reach, automated backups on. `db.t4g.medium` is plenty for today's data.
2. The **API**: the backend image (`backend/Dockerfile`) in ECR, run as `web` and `worker`
   (EC2 Auto Scaling, per owner decision 1), behind an Application Load Balancer with HTTPS
   (`api.luminaiq.fun`). Health check `/health`, readiness `/ready`.
3. **Settings** (Secrets Manager or SSM Parameter Store, never in git): everything in
   `.env.example`, with `DATABASE_URL` pointing at RDS, the same `SUPABASE_URL` /
   `SUPABASE_KEY` / `SUPABASE_SERVICE_KEY` as today, `SMALL_LLM_*`, `BIG_LLM_*`, `EMBEDDING_*`,
   `RAZORPAY_*`, `SECRET_KEY`.
4. The **website**: S3 + CloudFront (or Amplify), built with `VITE_MAIN_API_URL=https://api.luminaiq.fun/api/v1`.

### 2. Rehearsal (no downtime)
1. Get the Supabase connection string: Supabase → Project Settings → Database → Connection string,
   **Session pooler**, append `?sslmode=require`.
2. From a machine that can reach both databases (an API server works):
   ```bash
   cd backend
   SOURCE_DATABASE_URL='postgresql://…supabase…?sslmode=require' DATABASE_URL='postgresql://…rds…' \
     uv run python -m scripts.migrate_from_supabase --dry-run
   ```
   Check the plan, then run it without `--dry-run` into a **staging** RDS database and try the app
   against it (sign in, open a book, chat, take a quiz, school dashboard, a paid account).

### 3. Cut-over (about 15 minutes of maintenance)
1. Stop writes on the old API: scale `luminaiq-api` on Azure to 0 replicas (or show a maintenance page).
2. Run the migration into the production RDS database (same command, no `--dry-run`). It must print `Done.`
3. Start the AWS `web` and `worker`; check `/ready`; watch the re-index jobs finish (admin → Analytics → Health).
4. Point traffic at AWS: `api.luminaiq.fun` and `luminaiq.fun` in Cloudflare DNS; set the GitHub variable
   `ANDROID_API_URL` to the AWS API and ship an Android build.
5. Supabase → Authentication → URL Configuration: keep the site URLs (sign-in still runs there).
6. Keep the Supabase database untouched for 30 days as the fallback, then retire it.

### Don't merge `production-grade` into `main` before step 3
`main` deploys to Azure (`.github/workflows/azure.yml`), and this code can't start there: it needs
`DATABASE_URL` and the new model settings. Retire the Azure workflows when AWS serves traffic.

## Later
- Files to S3 (PDFs, book text, chat photos), then sign-in off Supabase (owner decision 2).
- AI provider on AWS (Bedrock) if "AWS only" should cover the models too: the app works with any
  OpenAI-compatible endpoint, set through `SMALL_LLM_*`, `BIG_LLM_*` and `EMBEDDING_*`.
