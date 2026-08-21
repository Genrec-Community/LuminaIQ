# LuminaIQ Backend Performance and Frontend Reliability Research

Date: 2026-08-22

## Scope and evidence standard

This report is tailored to the checked-out LuminaIQ repository. It recommends backend features and performance work that should make the product feel faster, plus frontend reliability fixes that preserve the current UI. No application source was changed.

Every recommendation separates:

- **Repository evidence:** behavior directly observed in this checkout.
- **Primary-source fact:** behavior documented by the owner of the platform, library, or standard, with a direct URL.
- **Repository-specific inference:** the expected LuminaIQ impact. This is a hypothesis to validate with the acceptance criteria, not a vendor guarantee.

Primary sources are limited to official project/vendor documentation, first-party source/documentation, and standards. Line references describe the checkout as inspected on the report date and may drift.

## Executive priorities

| Priority | Opportunity | Why it is first | Expected user effect |
| --- | --- | --- | --- |
| P0 | Make the deployed backend and frontend API target one explicit production origin | CI deploys Container Apps, but the built frontend always calls App Service | Users actually receive each backend release; cold-start and incident diagnosis become deterministic |
| P0 | Move document/graph work from process-local tasks to durable, claimable jobs and durable progress | Four Gunicorn workers and Container Apps replicas cannot share locks, semaphores, tasks, or SSE queues | Uploads survive restarts/deploys; progress no longer randomly disappears |
| P0 | Make Graph Build incremental, bounded-concurrent, and atomic | It currently force-deletes the graph, repeats overlapping LLM work serially, and can publish an empty/partial result | Much shorter document completion time without graph disappearance |
| P0 | Fix frontend auth refresh, error propagation, and retry semantics | A refresh request can wait on itself; initial project document failures are swallowed; POSTs are retried automatically | Fewer indefinite spinners, accidental duplicate mutations, and false “empty project” states |
| P1 | Remove repeated Qdrant collection/index discovery and validate the collection-per-project model | Every upload lists every collection and synchronously “ensures” two indexes | Lower ingestion setup latency and less Qdrant control-plane work |
| P1 | Tune Supabase/PostgREST query shape and indexes from measured plans | Hot list paths use `select("*")`; graph processing performs separate document-topic reads | Smaller responses and fewer database round trips |
| P1 | Add endpoint, job, and model observability tied to SLOs | Existing logs expose full URLs but do not provide stage latency, queue age, or model token metrics | Performance changes become measurable rather than anecdotal |
| P2 | Modernize ASGI lifecycle/middleware and right-size workers from load tests | Timeout and request logging add middleware work; worker count hard-codes multiplied limits | More predictable cancellation, shutdown, and capacity behavior |

## Implementation status

Implemented on `dev/rework-embedding`:

- CI/CD now targets the Azure App Service used by the frontend, embeds the Git
  commit in the deployed artifact, enables remote dependency build, verifies
  `/health`, and gates the frontend deployment on that check.
- Graph Build generates with process-wide bounded concurrency two, removes
  fixed sleeps, raises provider/parse failures, preserves the active graph on
  generation failure, and rejects stale cross-worker publication. Migrations
  004 and 006 provide atomic and ordered publication but remain unapplied.
- Qdrant uses direct collection existence checks, coordinates initialization
  per collection, and creates only missing payload indexes.
- Authentication, settings, and flashcard hot paths move synchronous Supabase
  work off the event loop. All LLM and RAG synthesis calls share one
  per-process provider concurrency gate with queue/provider timing logs.
- Request logs exclude query strings, FastAPI uses lifespan, request timing is
  pure ASGI, project-load failures propagate, semantic search is cancellable,
  and document progress has reconnect plus persisted-status polling fallback.
- JSX is included in ESLint with Rules of Hooks enforced and dependency issues
  reported. Remaining dependency warnings are visible technical debt.
- Migration 005, a lease-safe job module, and a standalone worker entrypoint
  establish the durable-job foundation. Both feature flags are false and the
  worker refuses to claim work until durable originals and pipeline integration
  exist.

Intentionally not activated or provisioned:

- Durable document processing cannot be enabled until the live Supabase schema,
  private original-document bucket, retention policy, and retry-safe pipeline
  stages are verified. Current uploads therefore retain their legacy path.
- Migrations 004-006 require review and application to the live Supabase project
  before their capabilities can be enabled.
- Database indexes require production `EXPLAIN` evidence; none were added
  blindly. Application Insights, alerting, new worker deployments, minimum
  replicas, PTUs, and other potentially billable resources were not created.
- Azure structured output requires confirmation that the deployed model and API
  version support the required schema before replacing repair parsing.

## Current-state findings

### Deployment topology is split

- **Repository evidence:** `frontend/src/api.js:5` hard-codes `https://luminaiq-api-v2.azurewebsites.net/api/v1`. `.github/workflows/ci-cd.yml:84-96` builds an immutable image and updates an Azure Container App. The frontend build does not pass or validate a backend URL.
- **Primary-source fact:** Vite exposes `VITE_` variables through `import.meta.env` and statically replaces them at build time; pre-existing build environment variables have highest priority. Values are public client configuration, not secrets ([Vite environment variables and modes](https://vite.dev/guide/env-and-mode)). Azure App Service unloads an app after 20 idle minutes when **Always On** is off, which can add warm-up latency; **Always On** keeps it loaded ([App Service general settings](https://learn.microsoft.com/en-us/azure/app-service/configure-common#configure-general-settings)). Azure Container Apps defaults to zero minimum replicas unless configured otherwise; setting at least one minimum replica ensures an instance is running ([Container Apps scaling](https://learn.microsoft.com/en-us/azure/container-apps/scale-app#scale-definition)).
- **Repository-specific inference:** CI can report a successful Container Apps deployment while every production browser continues using an older App Service deployment. The UI’s “backend may be waking up” behavior cannot be tuned confidently until one platform is authoritative.

### Background work and progress are process-local

- **Repository evidence:** `backend/api/v1/endpoints/documents.py:173` starts document processing with `asyncio.create_task`. `EmbeddingQueue` semaphores, jobs, and tasks; `EmbeddingBatchScheduler` semaphores and document locks; `TopicGraphBuilder` locks; and `ProgressManager` subscribers are Python-memory objects. `backend/startup.sh` starts four Gunicorn workers, and Container Apps can add replicas.
- **Primary-source fact:** FastAPI explicitly recommends a separate multi-process/multi-server job mechanism for heavy background computation rather than relying on in-process background tasks ([FastAPI Background Tasks caveat](https://fastapi.tiangolo.com/tutorial/background-tasks/#caveat)). Container Apps creates replicas when scaling out and can scale them down according to limits and rules ([Container Apps scaling](https://learn.microsoft.com/en-us/azure/container-apps/scale-app)). Container Apps deployments create immutable revisions; old revisions are deprovisioned in single-revision mode after the replacement is ready ([Container Apps revisions](https://learn.microsoft.com/en-us/azure/container-apps/revisions#revision-modes)).
- **Repository-specific inference:** an upload accepted by worker A can publish progress only to subscribers connected to worker A. A subscriber routed to worker B can wait forever. Two workers or replicas can also rebuild the same project concurrently because their “global” locks and limits are unrelated. A worker restart or revision replacement cancels unpersisted work while the document can remain `pending` or `processing`.

### Graph Build is serial, overlapping, destructive, and repeatedly forced

- **Repository evidence:** `TopicGraphBuilder` defaults to 25-topic batches with a five-topic overlap, executes each batch sequentially, and sleeps 0.5 seconds between batches (`backend/services/topic_graph_builder.py:42-44, 95-105`). `document_service.py:200-236` collects all project topics after every document and calls `build(..., force_rebuild=True)`. Forced builds delete all existing relationships before any LLM call (`topic_graph_builder.py:91-109`). Operational exceptions are converted to a success-shaped result instead of raised (`:118-120`), and the caller logs “built” without checking that message. The deterministic benchmark expects peak LLM concurrency of one and budgets up to 15 calls for five cumulative builds.
- **Primary-source fact:** Azure OpenAI latency is strongly influenced by model, generated token count, and load; lowering requested/generated output tokens reduces per-call latency. Azure recommends monitoring prompt tokens, generated tokens, time to response, and time to last byte, and notes that batching/concurrency must be tested against the workload ([Azure OpenAI performance and latency](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/latency)). Azure quotas are expressed in requests and tokens per minute, and Microsoft recommends retry logic, gradual load changes, load testing, and quota monitoring rather than assuming unlimited capacity ([Azure OpenAI quotas and limits](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/quotas-limits)). Structured outputs constrain responses to a supplied JSON Schema, unlike plain JSON mode, which does not enforce schema adherence ([Azure OpenAI structured outputs](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/structured-outputs)).
- **Repository-specific inference:** for 100 topics, five overlapping calls plus four artificial delays put total graph latency close to the sum of five LLM latencies. Rebuilding at 20, 40, 60, 80, and 100 topics repeats earlier inference and token costs. Deleting first creates an avoidable interval with no graph and makes an LLM outage capable of replacing a valid graph with nothing.

### Qdrant setup repeats global discovery and index creation

- **Repository evidence:** `QdrantService.create_collection` calls `get_collections()`, scans the complete collection list, and then calls two `create_payload_index(..., wait=True)` operations on every document upload (`backend/services/qdrant_service.py:54-95`). A collection is created per project.
- **Primary-source fact:** Qdrant provides a direct collection-existence endpoint/client method, avoiding a complete collection listing ([Qdrant collections: Check Collection Existence](https://qdrant.tech/documentation/concepts/collections/#check-collection-existence)). Qdrant recommends a single collection with payload-based partitioning for most multitenant use cases; many collections have resource overhead, though multiple collections can be appropriate for isolation with a limited tenant count ([Qdrant collections: multitenancy](https://qdrant.tech/documentation/concepts/collections/#setting-up-multitenancy)). Payload indexes consume compute and memory, should be limited to filter fields, and should be created before ingestion ([Qdrant indexing](https://qdrant.tech/documentation/concepts/indexing/#payload-index)).
- **Repository-specific inference:** setup cost grows with project count and is paid on every upload. The current collection-per-project choice may remain correct for isolation, but it should be an explicit measured decision rather than an unbounded default.

### Database and HTTP boundaries do unnecessary or unsafe work

- **Repository evidence:** document/project and many feature list paths use `select("*")`; graph assembly performs one query for completed documents and another for the current document. The synchronous Supabase client is correctly moved to a dedicated thread pool, but the pool has 64 threads per worker, so startup’s four workers can create up to 256 database-call threads per replica. `main.py` prints import-time filesystem/debug details and logs `request.url`, including query strings. The progress URL contains the app JWT.
- **Primary-source fact:** Supabase recommends aligning indexes with common filters, joins, and ordering, validating them with `EXPLAIN`, and avoiding over-indexing because indexes slow writes ([Supabase query optimization](https://supabase.com/docs/guides/database/query-optimization)). PostgREST supports range-based pagination and warns that exact counts become slower on large tables; planned or estimated counts trade exactness for speed ([PostgREST pagination and count](https://postgrest.org/en/stable/references/api/pagination_count.html)). HTTP’s security guidance says sensitive information in a URI can be disclosed through logs, history, caches, and intermediaries and recommends using header or content fields where possible ([RFC 9110 section 17.9](https://www.rfc-editor.org/rfc/rfc9110.html#section-17.9)).
- **Repository-specific inference:** response serialization and transfer grow unnecessarily as rows gain columns. Full URL logging exposes progress credentials and turns normal diagnostics into a credential-retention risk. Per-process thread and semaphore values make configured “global” limits misleading under load.

## Prioritized backend opportunities

### P0. Establish one production backend contract

**Recommendation:** choose Container Apps or App Service as the production authority. Given the existing CI, the smallest coherent path is to point Vercel builds at the Container Apps stable application URL through `VITE_MAIN_API_URL`, fail production builds when it is absent/invalid, and retain localhost only for development. If App Service remains authoritative instead, change CI to deploy and verify App Service rather than claiming Container Apps is production.

Use a stable custom API domain so a future platform migration changes DNS/configuration rather than source. Add a post-deploy check that compares the deployed backend’s revision/commit endpoint with `${{ github.sha }}` before deploying the frontend. Vite’s build-time replacement behavior supports this configuration ([Vite environment variables](https://vite.dev/guide/env-and-mode#env-variables)); Container Apps revisions are immutable snapshots suitable for revision identification ([Container Apps revisions](https://learn.microsoft.com/en-us/azure/container-apps/revisions)).

For “snappy” interactive use, set Container Apps `minReplicas >= 1`, or enable App Service Always On on a qualifying plan. Do not pay for both merely to hide the topology mismatch. Container Apps documents zero as the default minimum and at least one as the always-running setting ([Container Apps scaling](https://learn.microsoft.com/en-us/azure/container-apps/scale-app#scale-definition)); App Service documents the 20-minute unload behavior and Always On mitigation ([App Service general settings](https://learn.microsoft.com/en-us/azure/app-service/configure-common#configure-general-settings)).

**Operational implication:** production configuration becomes part of the release artifact. Rollback must restore a compatible frontend/backend pair or preserve API compatibility across revisions.

### P0. Introduce durable document jobs and durable progress

**Recommendation:** make the database the source of truth for job state before introducing another infrastructure product. On upload, atomically create a job row with `queued`, return HTTP 202 plus IDs, and have a dedicated worker claim jobs using a database function/transaction that prevents double claims. Persist attempts, lease owner, lease expiry, stage, percent, error, and heartbeat. A crashed worker’s expired lease becomes claimable. The API process should not own the job lifetime.

Use the same durable state for progress. The existing UI can preserve its visuals while either polling a lightweight status endpoint or subscribing to durable database changes; Supabase documents Postgres Changes subscriptions as database-change events ([Supabase Postgres Changes](https://supabase.com/docs/guides/realtime/postgres-changes)). FastAPI’s own caveat supports moving heavy work out of the request process when multiple processes or servers are involved ([FastAPI Background Tasks caveat](https://fastapi.tiangolo.com/tutorial/background-tasks/#caveat)).

Start with one worker process/replica and measured concurrency. Scale workers from queue depth only after leases and provider-wide limits exist. A semaphore in each replica cannot enforce an Azure-wide RPM/TPM limit; use a shared token budget or conservatively divide configured quota across maximum workers. Azure’s quotas are explicitly RPM/TPM based ([Azure OpenAI quotas and limits](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/quotas-limits)).

**Operational implication:** deploys no longer silently discard accepted jobs, but schema migration, stale-job reconciliation, poison-job handling, and retention become explicit responsibilities. Graceful shutdown should stop claims and allow a lease to expire or finish.

### P0. Redesign Graph Build around incremental input, bounded concurrency, and atomic publication

**Recommendation:** implement in this order:

1. Compute and persist a canonical topic-set fingerprint. Skip when unchanged.
2. Stop calling a forced full rebuild after each document. Queue one debounced/coalesced project graph job so rapid uploads produce one build for the newest topic set.
3. Generate independent batches concurrently behind a small configurable bound, initially two, with provider-aware backoff. Remove the fixed 0.5-second sleep; throttling should respond to real quota signals, not add unconditional latency. Azure recommends retries and gradual, tested load rather than assuming quota behavior ([Azure OpenAI quotas](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/quotas-limits#general-best-practices-to-remain-within-rate-limits)).
4. Request only the output required. The current target of roughly two edges per topic does not justify a blanket 4,000 output tokens per batch. Measure output distributions and lower the cap; Azure states generated tokens and requested generation size are major latency drivers ([Azure OpenAI latency: Generation size and max tokens](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/latency#generation-size-and-max-tokens)).
5. Use Azure structured outputs with a strict edge-array schema when supported by the deployed model/API, eliminating markdown stripping and truncated-JSON repair from the normal path ([Azure OpenAI structured outputs](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/structured-outputs)).
6. Publish atomically: generate and validate into a build/version staging set, then replace or switch the active graph in one database transaction. Never clear the active graph before inference succeeds.
7. Raise a failed job when any required batch fails. Do not convert errors to an apparently successful `{edges_created: 0}` result.

The overlap should be A/B tested. It can improve cross-boundary context, but in this implementation each prompt lists only `batch_topics`; `all_topics` is used only after inference to validate names. Therefore overlap necessarily repeats prompt topics and calls, while its quality benefit is unmeasured. Keep it only if graph-quality evaluation beats non-overlap or a two-pass strategy.

**Operational implication:** bounded parallelism lowers wall-clock time but raises instantaneous RPM/TPM. The benchmark must report actual peak concurrency and cannot calculate orchestration overhead as `elapsed - calls * latency` once calls overlap. Track graph version, source fingerprint, batch attempts, prompt/output tokens, and publication outcome.

### P1. Remove Qdrant control-plane work from every upload

**Recommendation:** replace `get_collections()` with the direct existence check, and create payload indexes only when a collection is first provisioned. Qdrant exposes `collection_exists` specifically for this ([Qdrant collection existence](https://qdrant.tech/documentation/concepts/collections/#check-collection-existence)). Keep indexes only for actual filters: `document_id` is clearly used; verify whether `chunk_id` filtering needs its own index under production cardinality. Qdrant states payload indexes consume additional compute/memory and should target filter fields ([Qdrant payload indexing](https://qdrant.tech/documentation/concepts/indexing/#payload-index)).

Later, load-test two models:

- Existing collection per project, measuring project-count control-plane latency and memory.
- One/shared few collections with a `project_id` tenant payload index and mandatory project filter.

Qdrant recommends payload-partitioned multitenancy for most cases but recognizes separate collections for limited tenants requiring isolation ([Qdrant multitenancy guidance](https://qdrant.tech/documentation/concepts/collections/#setting-up-multitenancy)). Security must not rely on a frontend filter; the backend must always enforce project ownership and add the project filter.

**Operational implication:** a shared collection reduces collection overhead but increases blast radius and makes filter/index correctness security-critical. Do not migrate without snapshot/restore and recall tests.

### P1. Shape Supabase/PostgREST queries and indexes from hot-path evidence

**Recommendation:** replace `select("*")` on project/document/dashboard paths with explicit UI fields, paginate growing lists, and combine the graph topic reads where practical. Candidate indexes to validate with `EXPLAIN (ANALYZE, BUFFERS)` include the actual ownership/list predicates, such as projects by `(user_id, created_at)`, documents by `(project_id, upload_status)`, and unique topic edges by `(project_id, from_topic, to_topic)`. Do not add them blindly: Supabase recommends matching indexes to filters/order/join patterns, checking plans, and avoiding write-costly over-indexing ([Supabase query optimization](https://supabase.com/docs/guides/database/query-optimization)).

Use bounded ranges for list endpoints. If a total is required, select exact, planned, or estimated PostgREST counts according to the UX need; exact counting can be slower on large tables ([PostgREST pagination and count](https://postgrest.org/en/stable/references/api/pagination_count.html)).

**Operational implication:** explicit response schemas become API contracts. Add migration scripts only after checking the live schema, because the repository’s SQL files are not a complete migration history.

### P1. Add stage-level observability and release gates

**Recommendation:** emit structured logs/metrics for request route templates, status, duration, job queue age, each pipeline stage, graph batch count/concurrency, Supabase/Qdrant latency, retries, Azure status codes, prompt/output tokens, and document/graph terminal outcomes. Never log authorization data or query strings containing credentials. RFC 9110 identifies URI disclosure through logs and intermediaries as a security risk ([RFC 9110 section 17.9](https://www.rfc-editor.org/rfc/rfc9110.html#section-17.9)).

Use Azure’s model metrics for `Time to Response`, `Time to Last Byte`, processed prompt tokens, and generated tokens; Microsoft explicitly recommends pairing latency and token metrics ([Azure OpenAI key latency metrics](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/latency#key-latency-metrics)). Add startup/readiness/liveness probes with different meanings: liveness is process responsiveness; readiness checks whether a replica should receive traffic; startup allows initialization time. Container Apps defines these probe roles and uses readiness during revision traffic shifts ([Container Apps health probes](https://learn.microsoft.com/en-us/azure/container-apps/health-probes)).

**Operational implication:** `/health` currently proves only that a request reached Python. Keep that cheap for liveness and add a separate readiness policy rather than making every liveness probe depend on all external vendors.

### P2. Simplify ASGI lifecycle, middleware, and process sizing

**Recommendation:** move startup/shutdown resource ownership to FastAPI’s `lifespan` context, close thread pools and async clients explicitly, remove import-time debug prints, and replace full-URL request prints with structured route-template logging. FastAPI recommends `lifespan`; `on_event` startup/shutdown is the deprecated alternative ([FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/)).

Replace or narrowly scope the `BaseHTTPMiddleware` timeout. Starlette documents that `BaseHTTPMiddleware` disrupts `contextvars` propagation and recommends pure ASGI middleware to avoid that limitation ([Starlette BaseHTTPMiddleware limitations](https://www.starlette.io/middleware/#limitations)). Prefer endpoint/provider timeouts and durable jobs for long operations over a blanket request timeout; verify cancellation reaches downstream work.

Do not apply the historical `(2 * cores) + 1` formula without measurement. The Docker startup hard-codes four workers and bypasses `GUNICORN_WORKERS`; each worker duplicates a 64-thread DB executor and all “global” limits. Run one Uvicorn process per constrained Container Apps replica initially, then scale replicas or workers from CPU, memory, p95 latency, queue depth, and provider quota. Also plan migration away from `uvicorn.workers.UvicornWorker`; Uvicorn marks that module deprecated and points to the separate `uvicorn-worker` package ([Uvicorn deployment: Gunicorn](https://www.uvicorn.org/deployment/#gunicorn)).

**Operational implication:** lowering workers may reduce accidental over-concurrency but requires load testing for synchronous extraction and Supabase thread usage. Durable workers should be separated from latency-sensitive API serving before aggressive scale-out.

## Frontend reliability fixes with no visual changes

### P0. Break the 401 refresh self-deadlock

- **Repository evidence:** the response interceptor handles 401 before excluding auth URLs. Its refresh path calls `api.post('auth/exchange', ...)` on the same intercepted instance. If that exchange returns 401 while `isRefreshing` is true, the exchange request is added to `refreshQueue`; the outer refresh waits for that queued request, and the queue is resolved only after the outer refresh completes.
- **Primary-source fact:** Axios response rejection interceptors run for non-2xx responses and interceptor chains apply to requests made by that instance ([Axios interceptors](https://axios-http.com/docs/interceptors)).
- **Recommendation:** exclude `/auth/` before entering refresh logic and perform exchange through a separate bare Axios instance (or a dedicated auth client with no refresh interceptor). Store one shared refresh promise rather than mutable boolean/queue coordination, and reject all waiters exactly once on failure.
- **Repository-specific inference:** this removes an indefinite request hang after an expired/invalid Supabase session while preserving all visible auth flows.

### P0. Propagate initial project-load failures

- **Repository evidence:** `ProjectView.initialLoad` wraps `await fetchDocuments()` in `try/catch`, but `fetchDocuments` catches its own error and returns `null`. The outer catch is unreachable. `null` becomes an empty document list, so a failed API call can look like an empty project and trigger topic loading.
- **Primary-source fact:** React recommends cleanup/ignore logic for effect-driven requests because responses can arrive in a different order from requests; effect cleanup runs before dependency changes and on unmount ([React `useEffect`: fetching data](https://react.dev/reference/react/useEffect#fetching-data-with-effects)). Axios supports `AbortController` through the `signal` request option ([Axios cancellation](https://axios-http.com/docs/cancellation)).
- **Recommendation:** let `fetchDocuments` reject (or return an explicit discriminated result), make `initialLoad` own the error state, and cancel/ignore obsolete project requests when `projectId` changes or the component unmounts. Apply the same pattern to dashboard/store searches where stale responses can overwrite newer state.
- **Repository-specific inference:** users see the existing error state instead of incorrect empty data, and rapid navigation cannot paint the prior project’s response into the next project.

### P0. Retry only operations that are safe or explicitly idempotent

- **Repository evidence:** the global interceptor retries network errors and 429/502/503 up to three times without checking the HTTP method. This includes create, import, evaluation, and AI-generation POSTs. The streaming chat function separately retries POSTs.
- **Primary-source fact:** HTTP defines PUT, DELETE, and safe methods as idempotent; clients may automatically retry idempotent requests after communication failure. A client should not automatically retry a non-idempotent request unless it knows the semantics are idempotent or can detect the original request was not applied ([RFC 9110 section 9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)). `Retry-After` communicates how long a client should wait after responses such as 503 ([RFC 9110 section 10.2.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-10.2.3)).
- **Recommendation:** automatically retry GET/HEAD/OPTIONS and explicitly approved idempotent operations only. For mutation POSTs that need retry, add a stable client-generated idempotency key and server-side result/deduplication record. Honor `Retry-After`, add jitter, and never replay a stream after user-visible chunks have arrived unless the protocol supports resume.
- **Repository-specific inference:** this prevents duplicate projects, imports, generated artifacts, or side effects during ambiguous gateway/network failures.

### P0. Make document progress reconnectable and durable

- **Repository evidence:** `EventSource.onerror` immediately calls `close()`, disabling browser reconnection, then `ProjectView` schedules only one document refresh. Progress events exist only in the producing process. One EventSource is opened per processing document. The JWT is included in the URL and `main.py` logs the complete URL.
- **Primary-source fact:** the EventSource standard automatically reestablishes eligible closed/network-failed connections and sends `Last-Event-ID` when events have IDs; calling `close()` sets state to `CLOSED` and stops reconnecting ([WHATWG EventSource interface and processing model](https://html.spec.whatwg.org/multipage/server-sent-events.html#the-eventsource-interface)). The standard also notes that clients can hit per-server connection limits and suggests sharing a connection where possible ([WHATWG SSE authoring notes](https://html.spec.whatwg.org/multipage/server-sent-events.html#authoring-notes)). Sensitive URI data can leak through logs and intermediaries ([RFC 9110 section 17.9](https://www.rfc-editor.org/rfc/rfc9110.html#section-17.9)).
- **Recommendation:** source progress from durable job state. Simplest first fix: poll all active document IDs through one endpoint with exponential backoff and visibility awareness. If retaining SSE, emit event IDs, support replay from durable state, allow automatic reconnection, and multiplex project progress over one connection. Replace the long-lived app JWT query parameter with authorization headers via fetch streaming, same-origin HttpOnly credentials, or a short-lived single-purpose progress token; redact query strings immediately regardless.
- **Repository-specific inference:** progress remains correct across transient network errors, worker routing, tab sleep, and deployments without changing the progress UI.

### P1. Make request cancellation and latest-response ownership consistent

- **Repository evidence:** long 120-180 second client timeouts accommodate cold starts and LLM requests, but most component effects do not abort requests on route/query changes. Search, project, and store state can therefore be updated by obsolete responses.
- **Primary-source fact:** Axios supports `AbortController` signals ([Axios cancellation](https://axios-http.com/docs/cancellation)); React’s official effect guidance uses cleanup to avoid stale network responses winning races ([React `useEffect`](https://react.dev/reference/react/useEffect#fetching-data-with-effects)).
- **Recommendation:** pass `signal` through API helpers used by effects; abort on cleanup; treat cancellation as neutral, not an error toast. Use request sequence ownership where a library cannot be canceled. Keep long timeouts only on endpoints that genuinely need them after durable jobs remove long request/response work.
- **Repository-specific inference:** fewer stale screens and less wasted backend work, especially during fast project navigation and search typing.

### P1. Bring JSX under lint and add transport/auth regression tests

- **Repository evidence:** `frontend/eslint.config.js` matches only `**/*.{ts,tsx}` while nearly all application code is `.jsx`; `npm run lint` therefore does not check the files containing auth, effects, and API calls. There is no frontend test script.
- **Primary-source fact:** React states its Hooks linter verifies reactive dependencies when configured, and missing/mismatched dependencies carry a high bug risk ([React effect dependencies](https://react.dev/reference/react/useEffect#specifying-reactive-dependencies)). ESLint flat config applies configuration objects according to their `files` patterns ([ESLint configuration files](https://eslint.org/docs/latest/use/configure/configuration-files#specifying-files-and-ignores)).
- **Recommendation:** include JS/JSX with browser globals and React Hooks rules, then add focused tests for refresh success/failure/concurrency, retry method filtering/idempotency, cancellation, ProjectView load failure, and progress reconnect/fallback. This changes no visual output.
- **Repository-specific inference:** CI begins checking the code where the identified reliability defects live instead of producing a false sense of frontend coverage.

## Operational implications

### Capacity is multiplicative today

With four workers, current configured maxima become up to 40 document pipelines, 60 embedding calls, 20 LLM calls, 80 Qdrant operations, and 256 Supabase executor threads **per Container Apps replica**, before replica scale-out. These are repository arithmetic, not measured safe capacities. Provider quotas and CPU/memory are shared outside each process. Replace “global” naming with `per_process` until shared coordination exists, then configure from measured end-to-end limits. Azure OpenAI requires monitoring RPM/TPM and warns bursty traffic can increase latency or produce 429s ([Azure OpenAI quotas](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/quotas-limits)).

### Deployment safety and work safety are separate

Container Apps can provide zero-downtime HTTP traffic switching when the new revision is ready ([Container Apps zero-downtime deployment](https://learn.microsoft.com/en-us/azure/container-apps/revisions#zero-downtime-deployment)), but that does not preserve Python `asyncio` tasks in a deprovisioned old revision. Durable jobs, leases, and idempotent stage writes are still required.

### Cold-start spending should follow topology alignment

Do not enable both App Service Always On and Container Apps minimum replicas as a first response. First prove which origin receives production traffic, then keep one API replica warm and measure dashboard/project p50/p95. Container Apps documents minimum replicas and billing tradeoffs ([Container Apps scale definition](https://learn.microsoft.com/en-us/azure/container-apps/scale-app#scale-definition)); App Service documents Always On behavior ([App Service general settings](https://learn.microsoft.com/en-us/azure/app-service/configure-common#configure-general-settings)).

### Data migrations need explicit rollout and rollback

Durable jobs, graph versions, idempotency keys, and new indexes need ordered migrations against the live Supabase schema. Backfill in bounded batches, deploy readers compatible with old and new state, then activate writers. Measure write amplification before adding indexes; Supabase explicitly notes the read/write tradeoff ([Supabase query optimization](https://supabase.com/docs/guides/database/query-optimization#over-indexing)).

### Security and reliability intersect at progress transport

Immediately stop logging complete URLs. Longer term, remove reusable JWTs from progress URLs. This is both a credential issue and a reliability issue: leaked/expired long-lived URLs complicate reconnect behavior. RFC 9110 recommends avoiding sensitive URI fields because URIs are widely retained ([RFC 9110 section 17.9](https://www.rfc-editor.org/rfc/rfc9110.html#section-17.9)).

## Measurable acceptance criteria

Measure on production-like Azure resources, with p95 calculated over at least 30 runs for pipeline benchmarks and over a representative traffic window for service metrics.

| Area | Acceptance criterion |
| --- | --- |
| Deployment target | A production build contains only the configured stable API origin; CI fails if the origin is missing; a post-deploy endpoint reports the deployed Git SHA and matches the workflow SHA |
| Warm responsiveness | With one warm production replica, `/health` p95 is under 250 ms and dashboard/project list API p95 is under 1 s, excluding the user’s last-mile network; cold-start latency is reported separately |
| Revision safety | A new revision receives no traffic before readiness succeeds; a deliberately failed readiness test leaves traffic on the prior revision, consistent with Container Apps revision behavior ([source](https://learn.microsoft.com/en-us/azure/container-apps/revisions#zero-downtime-deployment)) |
| Durable upload | Kill the API and worker after upload acceptance at each pipeline stage; the job is reclaimed after lease expiry and reaches exactly one terminal state without manual intervention |
| Duplicate prevention | Submit the same upload/mutation idempotency key concurrently 10 times across at least two processes; exactly one logical job/result is created and all callers receive the same outcome |
| Progress | Across worker restart, replica change, and a 30-second client disconnect, the existing progress UI resumes within 5 seconds and eventually shows the durable terminal state; no reusable JWT appears in request logs |
| Graph latency | For 100 topics with a controlled fake/provider latency, graph wall-clock p95 is at most `ceil(batch_count / concurrency) * per_call_p95 + 20%` orchestration allowance, with initial concurrency two; report actual RPM/TPM and 429 rate |
| Graph work budget | Upload sequence 20/40/60/80/100 topics no longer performs five forced full rebuilds; unchanged topic fingerprints make zero LLM calls; coalesced rapid uploads publish only the latest requested fingerprint |
| Graph atomicity | Inject one failed/truncated batch into a rebuild; readers continue receiving the prior complete graph, no active empty/partial graph is visible, and the job is failed/retryable |
| Graph quality | On a fixed evaluation corpus, removing/reducing overlap does not reduce valid-topic edge rate, topic coverage, or human-rated prerequisite precision by more than an agreed 2 percentage points |
| Structured output | On 100 fixed graph generations, at least 99% parse and schema-validate without repair; invalid/refused/truncated responses fail the batch rather than silently publishing zero edges |
| Qdrant setup | Existing-project upload performs no full collection listing and no payload-index creation; collection setup p95 is under 250 ms on the production-like cluster |
| Database | Hot project/document queries have explicit column lists and bounded ranges; measured plans avoid sequential scans once table size makes them material; each changed endpoint reduces response bytes or database time by at least 20% without result changes |
| Provider limits | Load test at configured maximum produces under 1% terminal 429/5xx after bounded retries and does not exceed the Azure deployment’s assigned RPM/TPM; queue age remains bounded |
| Auth refresh | 20 simultaneous 401s trigger one exchange; all requests resolve/reject within the normal timeout; a 401 from exchange rejects every waiter and redirects once, with no pending promises |
| Retry safety | Automated tests prove non-idempotent POSTs are attempted once without an idempotency key; GET retry honors `Retry-After`; mutation replay with a key creates one server-side result |
| React races | Navigating A to B while A is delayed never renders A data in B; unmount/route change aborts the obsolete request and cancellation shows no error state |
| Frontend CI | ESLint processes `.js`/`.jsx` application files with Hooks rules; focused transport/auth/progress tests run in CI and fail on reproductions of the four P0 frontend defects |

## Do now / later sequence

### Do now

1. **Align production:** choose the authoritative Azure backend, use and validate `VITE_MAIN_API_URL`, expose build SHA, run a post-deploy smoke check, and keep one authoritative backend instance warm.
2. **Stop immediate reliability failures:** redact query strings; fix auth exchange recursion; propagate `ProjectView` fetch failures; restrict automatic retries to safe/known-idempotent operations; enable JSX linting and focused regression tests.
3. **Make Graph Build safe before making it faster:** stop delete-first publication, fail jobs on batch failure, fingerprint/coalesce rebuilds, and update the benchmark to measure concurrency and repeated-work budgets.
4. **Then parallelize modestly:** run graph batches at bounded concurrency two, remove fixed sleeps, lower measured output caps, and adopt structured outputs if the deployed Azure model/API supports them.
5. **Remove easy hot-path overhead:** use Qdrant’s direct existence check, create indexes only on collection creation, shape project/document selects, and add measured database indexes through an explicit migration.

### Later

1. Move accepted document/graph execution to durable leased workers and make durable job state the progress source; separate API and worker scaling.
2. Multiplex or replace per-document SSE after durable progress exists; add replay/event IDs if SSE remains.
3. Load-test collection-per-project versus payload-partitioned Qdrant multitenancy before migration.
4. Tune worker/replica counts and shared Azure OpenAI rate budgets from SLO metrics, then consider provisioned throughput only if measured latency/throughput justifies it. Azure describes PTU as the predictable-capacity option for latency-critical/high-volume use ([Azure OpenAI usage-tier actions](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/quotas-limits#recommended-actions-if-you-exceed-your-usage-tier)).
5. Replace deprecated Uvicorn Gunicorn integration, adopt FastAPI lifespan, and simplify timeout middleware after durable jobs remove long request-bound operations.

## Decision summary

The fastest credible path is not a larger semaphore or more Gunicorn workers. It is to remove topology ambiguity, stop repeated/destructive graph work, and make accepted work durable. The current UI can remain visually unchanged while its transport becomes deterministic: one configured backend, explicit request outcomes, safe retries, cancellation, and progress derived from durable state. Only after those changes will graph concurrency, Qdrant layout, worker count, or Azure capacity tuning produce measurable speed without amplifying duplicate work and intermittent failures.
