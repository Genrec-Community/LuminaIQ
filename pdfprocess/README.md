# Lumina IQ - PDF Processing Service

PDF Processing microservice for the Lumina IQ education platform. Handles document upload, text extraction, and chunking. Designed to be deployed on Render.

## Features
- Upload PDF, DOCX, TXT, HTML, MD files
- Extract text using PyMuPDF4LLM (great for tables/structured content)
- Chunk text using LangChain RecursiveCharacterTextSplitter
- Store chunks in Supabase `document_chunks` table
- Notify main API via webhook when processing completes

## Deployment on Render

### 1. Create a New Web Service
- Connect your GitHub repository
- Set the root directory to `bac_proess`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### 2. Environment Variables
Set these in Render's environment settings:
```
SUPABASE_URL=your-url
SUPABASE_SERVICE_KEY=your-key
MAIN_API_WEBHOOK_URL=https://your-hf-space.hf.space/api/v1/webhook/document-ready
MAIN_API_WEBHOOK_SECRET=your-secret
CHUNK_SIZE=500
CHUNK_OVERLAP=50
```

### 3. Database Setup
Run the SQL in `db/schema.sql` in your Supabase SQL Editor to create the `document_chunks` table.

## Local Development

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn main:app --reload --port 8001
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/health` | Render health check |
| POST | `/upload` | Upload and process document |
| GET | `/documents/{project_id}` | List documents |
| DELETE | `/documents/{document_id}` | Delete document |

## Upload Example

```bash
curl -X POST "http://localhost:8001/upload" \
  -F "file=@document.pdf" \
  -F "project_id=your-project-id"
```
