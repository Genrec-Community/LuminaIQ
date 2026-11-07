# Phase 6: LaTeX and image input — implementation plan

> For agentic workers: follow test-driven-development; check boxes as tasks finish.

**Goal:** maths renders properly everywhere (chat, quizzes, flashcards, notes, mindmaps, lessons, PDF export), and a
student can photograph a question or diagram and get a cited (or clearly labelled) answer at their level.

**Architecture:**
- Frontend: one `components/Markdown.jsx` (remark-gfm + remark-math + rehype-katex, KaTeX CSS loaded once) replaces
  every direct `ReactMarkdown`. `utils/math.js` normalises `\( \)` / `\[ \]` to `$` / `$$` and hides an unfinished
  formula at the end of a streaming answer until it closes. Short strings (quiz options, flashcard sides, mindmap
  labels) use the same component in inline mode.
- Backend: `utils/json_latex.py` parses model JSON without losing LaTeX (`\frac` would otherwise become a form-feed
  plus "rac"); used by the quiz, flashcard and mindmap parsers.
- Image input: the chat request may carry one JPEG/PNG (data URL, client-resized to ≤1600 px). The backend checks the
  `image` tool and plan quota, stores it in the private `chat-images` bucket (best effort), asks the vision-capable
  model to transcribe the question and describe any diagram, uses that as the retrieval query, and answers as usual
  (book first, otherwise "Not from your book" when the class allows). School level: the vision step also flags
  unsafe images, and the transcript goes through the existing safety screen.

**Builder's calls:**
- Vision capability is declared in settings (`SMALL_LLM_VISION`, `BIG_LLM_VISION`, default false). The photo button is
  hidden for a learner whose model can't see images (free users use the small model; paid users the big one when set).
- Only the transcription step uses the vision model; the answer itself uses the normal chat model, so a photo costs
  one extra call, not a bigger answer.
- Photo questions are never served from or stored in the shared answer cache.
- New metered feature `image` (daily): free 5, scholar 30, topper 100, institution 30.

## Tasks
- [x] 1. `utils/json_latex.py` + tests; use it in quiz, flashcard and mindmap parsing.
- [x] 2. `Markdown.jsx` + `utils/math.js`; replace every `ReactMarkdown`; inline maths in quiz options, flashcards,
      mindmap labels, cram cards; KaTeX CSS in PDF export.
- [x] 3. Settings (`*_VISION`, `CHAT_IMAGE_MAX_BYTES`), plan feature `image`, tool availability by vision capability.
- [x] 4. Backend image pipeline in chat (validate, store, transcribe, moderate, retrieve, answer, save reference);
      history returns a signed thumbnail URL. Tests with the fake model server.
- [x] 5. Frontend: attach/camera button, client resize + JPEG, preview, thumbnail in the conversation.
- [x] 6. Fake server understands image messages; end-to-end and browser checks; AGENTS.md; push.
