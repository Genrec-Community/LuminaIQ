# Phase 7: Intelligent gamification — implementation plan

> For agentic workers: follow test-driven-development; check boxes as tasks finish.

**Goal:** XP rewards learning, not clicking; one adaptive goal a day; kind streaks; each level sees its own style;
teachers see who is stuck.

**Today:** the browser calls `award-xp` with an activity name and the server trusts it (chat 3 XP, notes 15, quiz up to
~120 depending on the score the browser reports). Opening tools earns XP; anything can be farmed.

**Architecture:**
- An append-only `xp_events` ledger (user, kind, xp, day, unique dedupe key). `gamification.award()` is the only way XP
  is granted: it applies the daily cap per kind, writes the ledger, updates `user_gamification`, the streak and badges.
- XP is granted **on the server, where learning is measured**:
  - `mastery_gain`: `learning_engine.record` — XP = the rise in a topic's mastery (in percentage points).
  - `mistake_fixed`: `learner_model.mark_fixed` — a previously wrong question answered right.
  - `review_on_time`: `SpacedRepetition.record_review` — a review done while the card was due.
  - `daily_goal`: the day's goal reached (once a day).
  - `exam_plan_step`: a learning-path topic completed for the first time (once per topic, ever).
  - `comeback`: first learning after a break of 3+ days (instead of a punishing reset).
- The old `award-xp` endpoint grants nothing: it returns the state plus XP events since the client's last sync, so
  the existing frontend hooks show toasts for real rewards.
- Daily caps per kind stop farming (`DAILY_CAPS`); dedupe keys stop repeats.
- Streak: counts days with any XP; one automatic freeze per ISO week covers a single missed day.
- Daily goal (`services/daily_goal.py`): "answer N questions", sized by level, the last 7 days' pace and days to the
  exam; focus = weakest topic and due reviews. Fixed for the day once created.
- Presentation (`style` in the API): `school` playful (celebrations, badges, class leaderboard if the tool is on),
  `higher_secondary` exam (countdown + goal), `ugpg`/`general` quiet stats, `research` milestones only (no confetti).
- Teacher view: the class dashboard flags students who are stuck — falling mastery, repeated mistakes or inactive —
  with the reason. Built from learning data only (never chats or memory notes).

## Tasks
- [x] 1. Schema `0009_gamification.sql`: `xp_events`, `daily_goals`.
- [x] 2. Rework `gamification_service.py`: rules, caps, `award()`, streak with freeze/comeback, learning badges,
      `state()` with style, goal and recent events. Tests (caps, dedupe, streaks, XP tracks mastery).
- [x] 3. Hooks: learning engine, mistakes, reviews, path completion. Tests.
- [x] 4. `services/daily_goal.py` + completion reward. Tests.
- [x] 5. API: sync endpoint (no client-granted XP), goal, class leaderboard (school level, tool-gated). Tests.
- [x] 6. Teacher "needs help" in the class dashboard. Tests.
- [x] 7. Frontend: context syncs and toasts real events; per-level panel, toasts and celebrations; daily goal card;
      leaderboard; Institution "Needs help". Browser check.
- [x] 8. AGENTS.md status; full tests; build; push.
