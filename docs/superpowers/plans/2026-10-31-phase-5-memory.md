# Phase 5: Memory and context — implementation plan

> For agentic workers: follow test-driven-development; check boxes as tasks finish.

**Goal:** the tutor remembers what matters about each student: their level and goals, what they're weak at and
which mistakes they make, and what was said earlier in a long chat. Students can see and delete what it remembers.

**Architecture:** three layers fed into one context builder.
1. Profile: existing settings plus level (unchanged).
2. Learner model (`services/learner_model.py`): weak/strong topics from `topic_mastery`, recent mistakes from a new
   `learner_mistakes` table (wrong quiz answers, tagged with a misconception by the small model in a background job).
3. Conversation memory (`services/memory.py`): a rolling `chat_summaries` row per project chat, refreshed by a
   background job every ~10 messages; long-term `user_memories` facts extracted in the same job for Class 11 and
   above only, deduplicated, capped per user, pruned after 6 months unused.

`context_builder.learner_block()` assembles layers 2–3 within `CONTEXT_BUDGET_MEMORY`; chat uses it (personal
answers only: cached shared answers stay neutral). Quizzes with no topic pick the student's weakest topic.

**Builder's calls:**
- Recent turns = everything after the summary's cut-off (at most 16), never fewer than the last 6: no gap between
  summary and history.
- Memories are chosen by word overlap with the question, then recency (no embeddings: at most 60 short facts).
- `memoryAcrossBooks` (default on) and `autoMemory` (default on) live in user settings. With across-books off,
  memories and mistakes from other books are not used; facts the student typed in themselves apply everywhere.
- Never extract sensitive facts (health, family problems, contact details, passwords).
- App state continuity: one `app_state` JSON row per user (`/user-data/state`), merged key by key, ≤ 64 KB.

## Tasks
- [x] 1. Schema `0006_memory.sql`: `chat_summaries`, `user_memories`, `learner_mistakes`, `app_state`.
- [x] 2. `services/learner_model.py`: weak/strong topics, recent mistakes, mistake recording + misconception job.
- [x] 3. `services/memory.py`: summary refresh, fact extraction (level-gated), CRUD, selection, pruning.
- [x] 4. `context_builder.learner_block()` + chat integration (summary + recent turns, learner block, job trigger).
- [x] 5. Quiz: record wrong answers on submit; no-topic quizzes target the weakest topic.
- [x] 6. API: `/memory` (list, add, edit, delete, clear, settings) and `/user-data/state`.
- [x] 7. Frontend: "What Lumina remembers about you" in Settings; resume last book/view and in-progress quiz.
- [x] 8. Tests (100-turn chat remembers turn 3; weak topics shape chat and quiz; delete works; teachers see none).
- [x] 9. `.env.example`, AGENTS.md status; full test run; frontend build; push.
