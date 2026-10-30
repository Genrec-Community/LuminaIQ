# Lumina IQ

> **Exams come faster than textbooks can be read. Lumina IQ turns any book into the shortest, smartest path to exam-ready.**

Upload a textbook and every feature works toward that one goal:

| Feature | How it serves the goal |
| --- | --- |
| **Exam Tonight** | Say how many hours you have. A planner weighs every topic by how much of the book it covers, how many other topics build on it and what you already know, then picks the plan worth the most marks in that time. It orders topics by prerequisite, adds breaks and gives you cram cards plus a one-page revision sheet. |
| **Learning path** | Topics ordered by a weighted topological sort, so each topic you learn makes the next one easier. Foundations come first and chapters stay together. |
| **Power Hour** | Bite-sized lesson cards with instant quiz checks, combos and XP. |
| **Visual Lab** | Any topic becomes a working interactive simulation (pendulum, light scattering, the heart…) with formulas, derivation and the why. |
| **Chat, quizzes, notes, flashcards, mindmaps** | Grounded in your own book, with citations. |
| **AI companion** | Name it, pick its personality, and it cheers you on in your style. |

## How topics are ordered and chosen

- `backend/services/topic_ordering.py` orders the path. It runs Kahn's algorithm over prerequisite edges and uses a priority queue that prefers *foundation* topics (a depth-damped count of how many topics build on each one), keeping chapters and book order together. Cycles are broken while dropping as little prerequisite weight as possible.
- `backend/services/cram_planner.py` picks topics for Exam Tonight. Each topic's value is `0.5·coverage + 0.35·foundation + 0.15`, and its cost is the minutes it takes to learn, which shrink with mastery. Selection is a precedence-constrained knapsack, solved greedily by *closure density*: a topic is only chosen together with its missing prerequisites. Leftover minutes buy skims, and a final slot is kept for revision.

## Layout

- `frontend/`: React + Vite, deployed on Vercel.
- `backend/`: FastAPI with Supabase (Postgres + storage), Qdrant vectors and any OpenAI-compatible LLM. Deployed on Render.
- `backend/migrations/`: SQL migrations, applied in order.
- `DEPLOY_TEST.md`: the test environment (test.luminaiq.fun) and its configuration.
