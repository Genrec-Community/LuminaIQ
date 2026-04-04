# LUMINAIQ - COMPLETE TECHNICAL DOCUMENTATION

## SECTION 1 — PROJECT OVERVIEW & PURPOSE

### What is LuminaIQ?

LuminaIQ is an **AI-powered intelligent learning platform** that transforms static educational documents (PDFs, DOCX, TXT) into interactive, personalized study experiences. It solves the problem of passive learning by providing students with AI-driven tools for active engagement, knowledge retention, and adaptive learning.

### Core Value Proposition

- **Problem Solved**: Students struggle with passive reading, poor retention, and lack of personalized study tools
- **Solution**: AI-powered document analysis that generates quizzes, flashcards, mind maps, knowledge graphs, and adaptive learning paths
- **Mission**: "Transform every document into an intelligent learning companion"

### Target Audience

- **Primary**: University students, self-learners, and professionals pursuing certifications
- **Secondary**: High school students preparing for exams
- **Persona Characteristics**: Tech-savvy, goal-oriented learners who value efficiency and personalization

### App Category

- **Type**: SaaS Web Application (Progressive Web App capabilities)
- **Platform**: Cross-platform (Web-based, mobile-responsive)
- **Deployment**: Cloud-hosted (Azure/Vercel)

### Maturity Level

- **Stage**: Growth/Production-grade MVP
- **Evidence**: Complete feature set, production deployment, error handling, monitoring
- **Gaps**: Limited analytics, no mobile native apps yet

### Monetization Model

[INFERRED] **Freemium** model based on:
- No payment gateway integration found in codebase
- Gamification system suggests engagement-focused growth
- Book Store feature indicates community/marketplace potential
- Likely future premium tiers for advanced AI features

---

## SECTION 2 — HIGH-LEVEL ARCHITECTURE

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      CLIENT LAYER                            │
│  React SPA (Vite) + TailwindCSS + Framer Motion            │
│  - Context API (Auth, Settings, Gamification, Toast)        │
│  - React Router (SPA routing)                                │
│  - Axios (HTTP client with retry logic)                      │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTPS/REST + SSE
┌──────────────────▼──────────────────────────────────────────┐
│                   API GATEWAY LAYER                          │
│  FastAPI (Python 3.11) - Async/Await                        │
│  - JWT Authentication Middleware                             │
│  - CORS Configuration                                        │
│  - Request Timeout Middleware (90s)                          │
│  - Retry Logic for 503/429 errors                           │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                 BUSINESS LOGIC LAYER                         │
│  Service Layer (Singleton Pattern)                          │
│  - AuthService, DocumentService, RAGService                  │
│  - MCQService, NotesService, FlashcardService               │
│  - KnowledgeGraphService, GamificationService               │
│  - LLMService, EmbeddingService                             │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                    DATA LAYER                                │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐│
│  │   Supabase     │  │   Qdrant     │  │  Azure OpenAI   ││
│  │   PostgreSQL   │  │  Vector DB   │  │  LLM + Embed    ││
│  │   + Auth       │  │              │  │                 ││
│  │   + Storage    │  │              │  │                 ││
│  └────────────────┘  └──────────────┘  └─────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Architecture Pattern

**Hybrid Monolith with Microservice Characteristics**

- **Monolithic Deployment**: Single FastAPI application
- **Service-Oriented Design**: Clear separation of concerns via service layer
- **Async/Non-Blocking**: Leverages Python asyncio for concurrency
- **Event-Driven Elements**: SSE for real-time progress, background task queues

**Why This Architecture?**
- Simplicity for MVP/growth stage
- Easy debugging and deployment
- Async Python provides sufficient concurrency
- Can be split into microservices later if needed

### Communication Protocols

- **REST API**: Primary communication (JSON over HTTPS)
- **Server-Sent Events (SSE)**: Real-time document processing progress
- **WebSocket**: Not currently used (SSE sufficient for one-way streaming)


### External Services & Integrations

| Service | Purpose | Why Chosen |
|---------|---------|------------|
| **Supabase** | PostgreSQL + Auth + Storage | All-in-one backend, RLS security, generous free tier |
| **Qdrant** | Vector database | Fast semantic search, open-source, Python-native |
| **Azure OpenAI** | LLM (GPT-4) + Embeddings | Enterprise-grade, reliable, reasoning models |
| **Azure Computer Vision** | OCR for images/scanned PDFs | Best-in-class accuracy, handles 50MB files |
| **Vercel** | Frontend hosting | Zero-config deployment, edge network, free tier |
| **Azure App Service** | Backend hosting | Python support, auto-scaling, integrated monitoring |

### Multi-Tenancy Model

**Row-Level Security (RLS)** via Supabase:
- Every table has `user_id` or `project_id` foreign key
- RLS policies enforce `auth.uid() = user_id` checks
- Backend uses service role key (bypasses RLS for admin operations)
- Client-side uses anon key (RLS enforced)

### Deployment Architecture

```
Frontend: Vercel Edge Network (Global CDN)
          ↓
Backend:  Azure App Service (West US)
          ├─ Gunicorn (3 workers)
          ├─ Uvicorn (ASGI server)
          └─ FastAPI app
          ↓
Database: Supabase (AWS us-east-1)
          ├─ PostgreSQL 15
          ├─ Auth (GoTrue)
          └─ Storage (S3-compatible)
          ↓
Vector DB: Qdrant Cloud / Self-hosted
AI:       Azure OpenAI (East US)
```

---

## SECTION 3 — TECH STACK (EXHAUSTIVE)

### Languages

| Language | Usage | Version | Why Chosen |
|----------|-------|---------|------------|
| **Python** | Backend | 3.11 | Async/await, rich AI/ML ecosystem, type hints |
| **JavaScript (JSX)** | Frontend | ES2022 | React ecosystem, wide browser support |
| **SQL** | Database | PostgreSQL 15 | Relational data, JSONB for flexibility |
| **Markdown** | Content | CommonMark + GFM | User-generated notes, AI outputs |

### Frontend Framework & Libraries

| Package | Version | Purpose |
|---------|---------|---------|
| **React** | 19.2.0 | UI framework (latest with concurrent features) |
| **React Router DOM** | 7.9.6 | Client-side routing |
| **Vite** | 7.2.4 | Build tool (fast HMR, optimized bundling) |
| **TailwindCSS** | 4.1.17 | Utility-first CSS framework |
| **Framer Motion** | 12.23.24 | Animation library (smooth transitions) |
| **Axios** | 1.13.2 | HTTP client (retry logic, interceptors) |
| **Lucide React** | 0.555.0 | Icon library (tree-shakeable, modern) |
| **React Markdown** | 10.1.0 | Markdown rendering (AI-generated content) |
| **Remark GFM** | 4.0.1 | GitHub Flavored Markdown support |
| **Cytoscape** | 3.33.1 | Knowledge graph visualization |
| **html2pdf.js** | 0.14.0 | Export notes/quizzes to PDF |
| **pdfjs-dist** | 4.4.162 | PDF viewing in browser |
| **@supabase/supabase-js** | 2.86.2 | Supabase client (auth, database, storage) |

### Backend Framework & Libraries

| Package | Version | Purpose |
|---------|---------|---------|
| **FastAPI** | 0.115.0 | Modern async web framework |
| **Uvicorn** | 0.27.0 | ASGI server |
| **Gunicorn** | 21.2.0 | Production WSGI server (process manager) |
| **Pydantic** | 2.12.5 | Data validation, settings management |
| **LangChain** | 0.3.27 | LLM orchestration framework |
| **LangChain OpenAI** | 0.3.35 | OpenAI integration for LangChain |
| **LangChain Qdrant** | 0.2.1 | Qdrant vector store integration |
| **Qdrant Client** | 1.16.1 | Python client for Qdrant |
| **Supabase** | 2.24.0 | Python client for Supabase |
| **PyJWT** | 2.10.1 | JWT token generation/validation |
| **Passlib** | 1.7.4 | Password hashing (bcrypt) |
| **Python-Jose** | 3.5.0 | JWT encoding/decoding |
| **PyMuPDF** | 1.26.6 | PDF text extraction |
| **python-docx** | 1.1.0 | DOCX file parsing |
| **BeautifulSoup4** | 4.12.3 | HTML parsing |
| **Pillow** | 11.3.0 | Image processing |
| **pytesseract** | 0.3.10+ | OCR fallback (local) |
| **pdf2image** | 1.17.0+ | PDF to image conversion |
| **aiofiles** | 23.2.1 | Async file I/O |
| **aiohttp** | 3.13.2 | Async HTTP client |

### Build Tools & Package Managers

- **Vite**: Frontend bundler (ESBuild-based, 10-100x faster than Webpack)
- **TypeScript Compiler**: Type checking (not transpiling, Vite handles that)
- **PostCSS**: CSS processing (Tailwind compilation)
- **Autoprefixer**: CSS vendor prefixing
- **npm**: Frontend package manager
- **pip**: Backend package manager

### Testing Frameworks

[UNCLEAR — needs confirmation]
- No test files found in codebase
- No pytest, jest, or vitest configuration
- **Recommendation**: Add unit tests (pytest for backend, vitest for frontend)

### Linting & Formatting

**Frontend:**
- **ESLint** (9.39.1): JavaScript/React linting
- **eslint-plugin-react-hooks**: React Hooks rules
- **eslint-plugin-react-refresh**: Fast Refresh compatibility

**Backend:**
- **Black** (25.11.0): Python code formatter (configured but not enforced in CI)

