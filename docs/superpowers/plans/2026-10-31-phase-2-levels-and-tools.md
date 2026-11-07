# Phase 2: Learner Levels, Tool Control and a Simpler App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [x]`) syntax.

**Goal:** Every learner has a level (Class 5–10 … PhD). The level decides the answer style and which tools they see. The platform admin sets tools per level, and institution admins narrow them per class.

**Architecture:**
- **Policies in Postgres.** Defaults live in code (`services/tools_catalog.py`). Rows override them: `level_tool_policies`, `level_settings`, `class_tool_policies`, plus class columns.
- **One function decides:** `services/levels.py: effective_for(user_id)` returns level, tools, hint mode and outside-book. It's cached briefly in the shared cache and cleared when a policy changes.
- **Enforced on the backend** with `require_tool("<key>")` (403 `tool_disabled`) and hidden on the frontend through `GET /levels/me`.
- **One prompt module** (`services/prompts/levels.py`) holds the level style, safety guardrails, hints-first and outside-book rules. It's used by chat and lessons.

**Spec:** `AGENTS.md` §5 Phase 2 and owner decisions 8–11 and 14–15.

## Global Constraints
- Levels: `school` (Class 5–10), `higher_secondary` (Class 11–12), `ugpg` (UG/PG), `research` (PhD/Research), `general`.
- Institution students take their class's level and can't change it. Individuals choose at sign-up and can change it in Settings.
- Tool keys are the app's existing tab IDs: `chat deep image qa quiz flashcards notes mindmap knowledge path cram power lab analytics pomodoro bookstore companion leaderboard`.
- Plan quotas (`services/plans.py`) keep working unchanged on top of the tool switches.
- Hints-first: off by default. Class `hint_mode` ∈ `always_on | always_off | student_choice`.
- Outside-book answers are allowed unless the level or class turns them off. They're labelled "Not from your book".

## Default tools (builder's call; the admin can change all of them)

| Tool | school | higher_secondary | ugpg | research | general |
| --- | --- | --- | --- | --- | --- |
| deep, knowledge, analytics, bookstore | off | on | on | on | on |
| leaderboard | on | on | off | off | off |
| everything else | on | on | on | on | on |

## Review Focus
1. An institution student with no class level set → falls back to their own chosen level, then to the `needs_level` prompt. Covered by `test_student_without_class_level_uses_own`.
2. A class turns on a tool the platform turned off for that level → stays off. Covered by `test_class_cannot_enable_platform_disabled_tool`.
3. A policy change takes effect at once (cache cleared). Covered by `test_policy_change_clears_cache`.
4. A school-level message about self-harm → caring reply with the helpline, no model call. Covered by `test_school_distress_gets_helpline`.
5. A teacher (not an admin) tries to change class tools → 403. Covered by `test_only_institution_admin_changes_class_settings`.

---

### Task 1: Schema, catalog and effective policy
**Files:** `db/schema/0003_levels_and_tools.sql`, `services/tools_catalog.py`, `services/levels.py`. Test: `tests/test_levels.py` (real Postgres).
- `effective_for(user_id) -> dict` returns `{level, level_label, locked, needs_level, tools: [..], hint_mode, hints_default, outside_book, class_id}`.
- [x] Tests:
  - `test_defaults_per_level`
  - `test_platform_override`
  - `test_class_narrows_tools`
  - `test_class_cannot_enable_platform_disabled_tool`
  - `test_student_takes_class_level_and_is_locked`
  - `test_student_without_class_level_uses_own`
  - `test_no_level_needs_level`
  - `test_policy_change_clears_cache`

### Task 2: APIs and enforcement
**Files:** `api/v1/endpoints/levels.py` (`GET /levels/catalog`, `GET /levels/me`, `PUT /levels/me`), `platform.py` (`GET /platform/levels`, `PUT /platform/levels/{level}`), `institutions.py` (`GET/PUT /institutions/classes/{class_id}/settings`, admin only), `utils/tools.py: require_tool(key)`, applied to chat (and `deep` when `deep=true`), quiz, qa, notes, flashcards, mindmap, cram, lab, power, knowledge, path.
- [x] Tests:
  - `test_me_endpoint_shapes`
  - `test_locked_student_cannot_change_level`
  - `test_disabled_tool_returns_403`
  - `test_platform_admin_updates_level`
  - `test_only_institution_admin_changes_class_settings`

### Task 3: Level-aware answers, hints, outside-book, safety
**Files:** `services/prompts/levels.py`, `services/safety.py`, `api/v1/endpoints/chat.py` (`ChatRequest.hints: Optional[bool]`), `services/rag_service.py` (outside-book rule replaces "I couldn't find…" when allowed), `api/v1/endpoints/lessons.py`.
- `safety.screen(text, level) -> Optional[str]` returns a canned caring reply for distress at the school level. Optional moderation API when `MODERATION_BASE_URL`/`MODERATION_API_KEY` are set. Only counts go to `safety_events`.
- [x] Tests:
  - `test_level_block_in_system_prompt`
  - `test_hints_resolution`
  - `test_outside_book_rule_toggles`
  - `test_school_distress_gets_helpline`
  - `test_safety_only_for_school`

### Task 4: Frontend
- `context/ToolsContext.jsx` (fetches `/levels/me`, exposes `has(tool)`, `level`, `needsLevel`, `refresh`).
- Hide tools in `SidebarNav`, `ProjectView` (APP_TOOLS), `mobile/screens/Book.jsx`, `mobile/screens/Home.jsx` and `chat/ChatCommands.jsx`.
- `LevelPicker` component: an onboarding step plus a blocking modal when `needsLevel`. Settings shows the level, read-only when locked.
- Platform: a "Levels & tools" section with one page per level (`/platform/levels/:level`).
- Institution: per-class settings panel.
- Chat menu: hints toggle when `hint_mode === 'student_choice'`.
- School level: a simple home with 4 big cards, larger text and fewer nav items.
- Remove `MemoryCurve` from the Dashboard, AdaptivePlan and mobile Home.
- [x] Verify: `npm run build` and `npm run lint` (no new errors). Click through in a browser (Playwright screenshots).
