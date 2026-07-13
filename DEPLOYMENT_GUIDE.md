# LuminaIQ — Comprehensive Cloud Deployment & Architecture Guide

This guide covers the complete architecture, environment configuration (including a single unified variable for AI Model APIs), step-by-step cloud deployment instructions for **Render**, **Vercel**, **AWS**, and **Azure**, and critical fixes applied to prevent deployment or runtime failures.

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Unified Model API Configuration & Environment Variables](#2-unified-model-api-configuration--environment-variables)
   - [Single Variable Model API (`MODEL_API_KEY`)](#single-variable-model-api)
   - [Backend `.env.example`](#backend-envexample)
   - [Frontend `.env.example`](#frontend-envexample)
3. [Bugs Fixed for Cloud Deployment](#3-bugs-fixed-for-cloud-deployment)
4. [Step-by-Step Deployment Guide](#4-step-by-step-deployment-guide)
   - [Option 1: Vercel (Frontend) + Render (Backend Docker)](#option-1-vercel-frontend--render-backend-docker)
   - [Option 2: Microsoft Azure (Recommended for Startup Credits)](#option-2-microsoft-azure-recommended-for-startup-credits)
   - [Option 3: Amazon Web Services (AWS)](#option-3-amazon-web-services-aws)
5. [Post-Deployment Troubleshooting Checklist](#5-post-deployment-troubleshooting-checklist)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      LuminaIQ Frontend                      │
│            React + Vite + TailwindCSS (SPA)                 │
│              Hosted on: Vercel / Azure SWA                  │
└──────────────┬──────────────────────────────┬───────────────┘
               │ HTTPS REST / SSE             │ Supabase Auth
               ▼                              ▼
┌──────────────────────────────┐    ┌─────────────────────────┐
│       LuminaIQ Backend       │    │    Supabase Cloud       │
│     FastAPI + Gunicorn       │    │ PostgreSQL + Auth +     │
│   Hosted on: Render / Azure  │    │      File Storage       │
│   Container Apps / AWS ECS   │    └─────────────────────────┘
└──────────────┬───────────────┘
               │
       ┌───────┴────────────────────────┬─────────────────────────┐
       ▼                                ▼                         ▼
┌─────────────────────────────┐  ┌─────────────────────┐  ┌───────────────────────┐
│     Azure OpenAI / LLM      │  │ Azure Computer Vis. │  │     Qdrant Cloud      │
│  GPT-4.1-mini & Embeddings  │  │ Cloud OCR Service   │  │   Vector Database     │
└─────────────────────────────┘  └─────────────────────┘  └───────────────────────┘
```

- **Frontend (`/frontend`)**: React 18 + Vite SPA communicating with backend REST endpoints and Supabase for authentication.
- **Backend (`/backend`)**: High-performance asynchronous FastAPI server using LangChain, Gunicorn + Uvicorn workers, and dedicated thread pools for vector embedding and retrieval.
- **AI / OCR Engines**: Supports **Azure OpenAI** (primary for Founders Hub credits) and standard **OpenAI / OpenRouter** compatible APIs, with cloud OCR via Azure Computer Vision or local OCR via poppler/tesseract.

---

## 2. Unified Model API Configuration & Environment Variables

### Single Variable Model API
You can now configure your AI models with a **single environment variable**:
```env
MODEL_API_KEY="your-api-key-here"
```
When `MODEL_API_KEY` is provided:
- If `AZURE_OPENAI_ENDPOINT` is configured, both `LLMService` and `EmbeddingService` automatically use `MODEL_API_KEY` to authenticate against your Azure OpenAI resource.
- If `AZURE_OPENAI_ENDPOINT` is not set, `MODEL_API_KEY` automatically authenticates OpenAI-compatible or OpenRouter LLM and embedding providers.

---

### Backend `.env.example`
Located at `backend/.env.example`:

```ini
# ==============================================================================
# 1. SINGLE UNIFIED MODEL API KEY
# ==============================================================================
MODEL_API_KEY=your-model-api-key-here

# ==============================================================================
# Option A: Azure OpenAI Configuration (Microsoft Founders Hub / Azure credits)
# ==============================================================================
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-openai-api-key
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini
AZURE_OPENAI_EMBED_DEPLOYMENT=text-embedding-3-small
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# ==============================================================================
# Option B: Standard / OpenRouter / OpenAI-Compatible Configuration (Fallback)
# ==============================================================================
LLM_API_KEY=your-llm-api-key
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=z-ai/glm-4.5-air:free

EMBEDDING_API_KEY=your-embedding-api-key
EMBEDDING_BASE_URL=https://openrouter.ai/api/v1
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# ==============================================================================
# 2. Supabase Configuration (Database & Storage)
# ==============================================================================
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_KEY=your-supabase-service-key

# ==============================================================================
# 3. Vector Database & Cloud OCR
# ==============================================================================
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

AZURE_CV_ENDPOINT=https://<region>.api.cognitive.microsoft.com/
AZURE_CV_KEY=

# ==============================================================================
# 4. Application Server Configuration
# ==============================================================================
ENVIRONMENT=production
PORT=8000
SECRET_KEY=your-super-secret-key-change-in-production
BACKEND_CORS_ORIGINS=http://localhost:5173,https://your-app.vercel.app
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=10485760
```

---

### Frontend `.env.example`
Located at `frontend/.env.example`:

```ini
# 1. Backend API Endpoint (Trailing /api/v1 required)
VITE_MAIN_API_URL=https://your-backend.onrender.com/api/v1

# 2. Supabase Configuration (Authentication & Client APIs)
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
```

---

## 3. Bugs Fixed for Cloud Deployment

Prior to deployment, the following critical bugs in the codebase were identified and resolved:

1. **Docker & Render System OCR Dependencies Fixed (`backend/Dockerfile`, `render.yaml`)**:
   - *Issue*: Document parsing libraries (`pdf2image`, `pytesseract`) crashed on cloud containers due to missing C++ binaries (`poppler-utils` and `tesseract-ocr`). On Render Native Python environments, running `apt-get` failed with non-root permission errors.
   - *Fix*: Updated `backend/Dockerfile` to install `poppler-utils`, `tesseract-ocr`, `build-essential`, and `libpq-dev` cleanly, and updated `render.yaml` to use `runtime: docker`.

2. **Azure vs. Fallback Embeddings Crash Fixed (`backend/services/embedding_service.py`)**:
   - *Issue*: `EmbeddingService.__init__` unconditionally instantiated `AzureOpenAIEmbeddings`, which raised an error on startup if `AZURE_OPENAI_ENDPOINT` was not set.
   - *Fix*: Added automatic fallback to standard `OpenAIEmbeddings` when Azure endpoint is omitted, resolving unified `MODEL_API_KEY`.

3. **String CORS Origins Parsing (`backend/config/settings.py`)**:
   - *Issue*: Passing comma-separated CORS domains (common in Render/AWS environment configuration) failed validation in Pydantic Settings.
   - *Fix*: Added a pre-validator that parses comma-separated strings or JSON arrays into a list of origins automatically.

4. **Line Ending Standardization (`backend/Dockerfile`)**:
   - *Issue*: Windows CRLF line endings in `startup.sh` caused `/bin/sh: \r: command not found` on Linux containers.
   - *Fix*: Added `sed -i 's/\r$//' startup.sh` to the Docker image build process.

---

## 4. Step-by-Step Deployment Guide

### Option 1: Vercel (Frontend) + Render (Backend Docker)

#### Step 1: Deploy Backend to Render
1. Push your repository to **GitHub**.
2. Log into **[Render Dashboard](https://dashboard.render.com/)** → Click **New +** → **Blueprint** (or **Web Service**).
3. Select your repository. If using Blueprint, Render will automatically read `render.yaml` and configure Docker runtime.
4. Under **Environment Variables**, add:
   - `MODEL_API_KEY` (or `AZURE_OPENAI_API_KEY` / `LLM_API_KEY`)
   - `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_DEPLOYMENT` (if using Azure OpenAI)
   - `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`
   - `BACKEND_CORS_ORIGINS`: Set to your frontend URL (e.g., `https://your-app.vercel.app`)
5. Deploy service. Once live, copy your backend URL (e.g., `https://luminaiq-backend.onrender.com`).

#### Step 2: Deploy Frontend to Vercel
1. Log into **[Vercel Dashboard](https://vercel.com/)** → **Add New Project** → Import your repository.
2. Set **Root Directory** to `frontend`.
3. Under **Environment Variables**, add:
   - `VITE_MAIN_API_URL`: `https://luminaiq-backend.onrender.com/api/v1`
   - `VITE_SUPABASE_URL`: Your Supabase URL
   - `VITE_SUPABASE_ANON_KEY`: Your Supabase Anon Key
4. Click **Deploy**.

---

### Option 2: Microsoft Azure (Recommended for Startup Credits)

Leveraging your **$880 – $150,000 Microsoft Founders Hub / Azure Credits**:

#### Step 1: Create Azure OpenAI Resource
1. In Azure Portal, search for **Azure OpenAI** → **Create**.
2. Go to **Model Deployments (Azure AI Studio)**:
   - Deploy `gpt-4o-mini` or `gpt-4.1-mini` (note deployment name e.g. `gpt-4.1-mini`).
   - Deploy `text-embedding-3-small` (note deployment name e.g. `text-embedding-3-small`).
3. Copy the **Endpoint URL** and **API Key**.

#### Step 2: What to do BEFORE running `az containerapp create` (Prerequisites & Container Build)
Before running the deployment command, you must create a resource group, container registry, and build your container image:

1. **Log in to Azure CLI**:
   ```powershell
   az login
   ```
2. **Create a Resource Group** (if you don't have one already):
   ```powershell
   az group create --name LuminaIQ-RG --location eastus
   ```
3. **Create an Azure Container Registry (ACR)** to host your Docker image:
   ```powershell
   az acr create --resource-group LuminaIQ-RG --name luminaiqacr --sku Basic
   ```
4. **Build your Docker container image in the Cloud (no local Docker required)**:
   Run this from your workspace root directory:
   ```powershell
   az acr build --registry luminaiqacr --image luminaiq-backend:latest ./backend
   ```
   *(Alternatively, if using local Docker Desktop: `docker build -t luminaiq-backend ./backend` followed by `az acr login --name luminaiqacr`, tag and push).*

5. **Deploy to Azure Container Apps**:
   Now that your image is built and stored in ACR, run:
   ```powershell
   az containerapp create `
     --name luminaiq-backend `
     --resource-group LuminaIQ-RG `
     --image luminaiqacr.azurecr.io/luminaiq-backend:latest `
     --target-port 8000 `
     --ingress 'external' `
     --env-vars `
         MODEL_API_KEY="your-azure-openai-key-here" `
         AZURE_OPENAI_ENDPOINT="https://liq.openai.azure.com/" `
         AZURE_OPENAI_DEPLOYMENT="gpt-5-mini" `
         AZURE_OPENAI_EMBED_DEPLOYMENT="text-embedding-3-small" `
         SUPABASE_URL="https://bcosfvilvwyxtrctsmez.supabase.co" `
         SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJjb3Nmdmlsdnd5eHRyY3RzbWV6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY3ODIyMTMsImV4cCI6MjA4MjM1ODIxM30.bj9wwAT41fkvGX6CLrmyQT16-Fph4_mgqSXZintsNX0" `
         SUPABASE_SERVICE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJjb3Nmdmlsdnd5eHRyY3RzbWV6Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2Njc4MjIxMywiZXhwIjoyMDgyMzU4MjEzfQ.Fyog6EUERO2Uo7EhlOHQAkRIXnQQEP8e-Klig9kp8I4"
   ```

#### Step 3: Deploy Frontend to Azure Static Web Apps
1. In Azure Portal → **Static Web Apps** → **Create**.
2. Connect your GitHub repository, select `frontend` folder as App location, `dist` as Output location.
3. Add environment variables `VITE_MAIN_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` under Configuration.

---

### Option 3: Amazon Web Services (AWS)

#### Step 1: Backend on AWS App Runner (Fastest Container Deployment)
1. Push your container image to **Amazon ECR**:
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com
   docker build -t luminaiq-backend ./backend
   docker tag luminaiq-backend:latest <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com/luminaiq-backend:latest
   docker push <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com/luminaiq-backend:latest
   ```
2. In AWS Console → **App Runner** → **Create Service**:
   - Source: Amazon ECR image.
   - Port: `8000`.
   - Add all environment variables (`MODEL_API_KEY`, `SUPABASE_URL`, `BACKEND_CORS_ORIGINS`).

#### Step 2: Frontend on AWS Amplify
1. In AWS Console → **AWS Amplify** → **New App** → Host web app.
2. Connect your GitHub repo (`frontend` directory).
3. Add environment variables under **App settings** → **Environment variables**.

---

## 5. Post-Deployment Troubleshooting Checklist

| Symptom | Cause | Solution |
| :--- | :--- | :--- |
| **CORS Error in Browser Console** | `BACKEND_CORS_ORIGINS` missing frontend domain | Add exact production URL (`https://your-app.vercel.app`) to `BACKEND_CORS_ORIGINS` in backend env variables without trailing slash. |
| **OCR / PDF Upload Fails (500 Error)** | Missing system OCR packages | Ensure backend is deployed via **Docker** (`backend/Dockerfile`) which contains `poppler-utils` and `tesseract-ocr`. |
| **Supabase Auth Redirect 404** | Site URL not whitelisted in Supabase | In Supabase Dashboard → **Authentication** → **URL Configuration**, add your deployed Vercel/Azure domain to **Redirect URLs**. |
| **504 Gateway Timeout on AI Generation** | Reverse proxy timeout exceeded | Long LLM operations stream progress. Ensure reverse proxy timeout is set to at least 90 seconds (Azure Container Apps default is 300s). |
