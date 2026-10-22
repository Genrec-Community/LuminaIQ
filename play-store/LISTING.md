# LuminaIQ — Google Play listing

Everything Play Console asks for, ready to paste. Graphics are in this folder.

| Asset | File | Play requirement |
|---|---|---|
| App icon | `icon-512.png` | 512 × 512 PNG |
| Feature graphic | `feature-graphic.png` | 1024 × 500 |
| Phone screenshots | `screenshots/01…07` | 1080 × 1920 (9:16), 2–8 images |

## Store listing

**App name** (30 max)
LuminaIQ: Study Smarter

**Short description** (80 max)
Turn your books and notes into quick questions, flashcards and a daily habit.

**Full description**
Your books, turned into a daily habit.

LuminaIQ reads your study material and turns it into short, swipeable practice you'll actually keep up with. Add a PDF, your notes, a scanned textbook or just paste text, and in about a minute you get questions, flashcards and a study buddy that knows your book.

LEARN IN MINUTES A DAY
• A swipeable feed of quick questions and flashcards made from YOUR material
• Wrong answers come back later at the right time (spaced repetition), so they stick
• Daily goals, streaks and XP keep you going, with one gentle reminder a day

ASK YOUR BOOK ANYTHING
• Chat with your study buddy and get answers with the exact passage they came from
• Explain it simply, give an example, quiz me: whatever helps it click

EVERY STUDY TOOL IN ONE PLACE
• Exam Tonight: a revision plan that fits the time you have left
• Power Hour: the fastest way through a whole book
• Notes, mind maps, flashcards, quizzes and written-answer practice with feedback
• Visual Lab: interactive simulations and scenarios that fit the topic
• Learning path and knowledge graph to see how ideas connect

WORKS WITH WHAT YOU HAVE
• PDFs (including scanned pages), Word documents and plain text
• Free books from the library to start right away

Built for students preparing for school, college and competitive exams, professionals studying for certifications, and anyone who wants to remember what they read.

**Category:** Education
**Tags:** study, flashcards, exam preparation, education
**Contact email:** (your support email)
**Privacy policy URL:** `https://test.luminaiq.fun/privacy` for now, then `https://luminaiq.fun/privacy` once the website is updated from this branch.

## App content (Policy → App content)

**Privacy policy:** the URL above.

**App access:** "All or some functionality is restricted" → add a test login (an email + password account you create for Google's reviewers) with the instruction "Sign in with email, choose *Use a password instead*".

**Ads:** No, the app contains no ads.

**Content rating questionnaire:** Category *Reference, News, or Educational*. Answer **No** to violence, sexual content, profanity, drugs and gambling. Users can interact (chat with AI): answer **No** to user-to-user communication (the chat is with an AI, not other users). Shares location: No. Digital purchases: No (purchases are on the website only).

**Target audience:** 13–15, 16–17 and 18+. Do **not** select under 13 (that triggers the Families policy). Appeals to children: No.

**News app:** No. **COVID-19 app:** No. **Government app:** No. **Financial features:** None. **Health:** No.

**Data safety** (what the app collects; all **encrypted in transit**, users **can request deletion** in the app: You → Delete account):

| Data type | Collected | Shared | Purpose | Optional? |
|---|---|---|---|---|
| Personal info → Name | Yes | No | App functionality, Account management | Optional |
| Personal info → Email address | Yes | No | Account management | Required |
| Files and docs | Yes | No* | App functionality | Required for the core feature |
| App activity → App interactions | Yes | No | App functionality, Analytics | Required |
| App activity → Other user-generated content (chat messages, notes) | Yes | No* | App functionality | Optional |
| App info and performance → Crash logs | Yes | No | App functionality | Required |

\* Processed by service providers on LuminaIQ's behalf (AI models, OCR, hosting). Google counts processing by service providers as **not sharing**.
Not collected: location, contacts, photos/videos (only files the user picks), audio, financial info, health, messages, calendar, device IDs for ads.

## Publishing steps

1. **Signing (once):** add the 4 GitHub secrets from `play-store-keys/SECRETS.txt` (Settings → Secrets and variables → Actions). The next build produces `LuminaIQ-release.aab`. Back up the keystore; Play App Signing protects you if it's ever lost (Google can reset the upload key).
2. **Create the app** in Play Console: *Create app* → name LuminaIQ, App, Free, accept declarations.
3. **First upload by hand** (Google requires this for a new app): Testing → Internal testing → Create release → upload `LuminaIQ-release.aab` from the latest build's Artifacts → add your testers' emails → Roll out.
4. **Automatic uploads from then on:** Play Console → Setup → API access → create a service account in Google Cloud with the *Release manager* permission on this app, download its JSON key, and save it as the GitHub secret `PLAY_SERVICE_ACCOUNT_JSON`. Every build then goes to Internal testing automatically. Set the repository variable `PLAY_TRACK` to `alpha` (closed testing) or `production` when you're ready.
5. **New personal developer accounts:** run a closed test with at least 12 testers for 14 days before applying for production. Organisation accounts can go straight to production.
6. **Google sign-in in the app:** Supabase → Authentication → URL Configuration → Redirect URLs → add `fun.luminaiq.app://login-callback`.
