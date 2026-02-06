import os
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from config.settings import settings
from services.document_processor import document_processor
from db.client import supabase_client
from utils.logger import logger

# Create temp directory if it doesn't exist
os.makedirs("temp", exist_ok=True)

app = FastAPI(
    title="Lumina IQ PDF Processing Service",
    description="PDF Processing Service for Lumina IQ - Handles file upload, text extraction, and chunking",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from datetime import datetime

class DocumentUploadResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    file_type: str
    file_size: int
    upload_status: str
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    service: str


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint"""
    return {"status": "healthy", "service": "pdf-processing"}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check for Render"""
    return {"status": "healthy", "service": "pdf-processing"}


@app.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: str = Form(...),
):
    """
    Upload a document and start processing it.
    Extracts text, chunks it, and stores chunks in Supabase.
    Then notifies main API to generate embeddings.
    """
    temp_file = None
    try:
        # 1. Validate File Type (MIME & Extension)
        allowed_mimes = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "text/html",
            "text/markdown"
        ]
        if file.content_type not in allowed_mimes:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, 
                "Invalid file type. Only PDF, DOCX, TXT, HTML, and MD are supported."
            )
        
        file_ext = os.path.splitext(file.filename)[1].lower().replace('.', '')
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, 
                f"Invalid file extension. Allowed: {settings.ALLOWED_EXTENSIONS}"
            )

        # 2. Secure Temp File Creation
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}", dir="temp")
        
        # 3. Stream content to check size
        file_size = 0
        chunk_size = 1024 * 1024  # 1MB chunks
        
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > settings.MAX_FILE_SIZE:
                temp_file.close()
                os.unlink(temp_file.name)
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, 
                    f"File size exceeds limit of {settings.MAX_FILE_SIZE} bytes"
                )
            temp_file.write(chunk)
            
        temp_file.close()
        temp_path = temp_file.name
            
        # 4. Create document record in Supabase
        doc_data = {
            "project_id": project_id,
            "filename": file.filename,
            "file_type": file.content_type,
            "file_size": file_size,
            "upload_status": "pending"
        }
        
        response = supabase_client.table("documents").insert(doc_data).execute()
        
        if not response.data:
            raise HTTPException(500, "Failed to create document record")
            
        document = response.data[0]
        document_id = document["id"]
        
        # 5. Start background processing
        background_tasks.add_task(
            document_processor.process_document,
            document_id=document_id,
            project_id=project_id,
            file_path=temp_path,
            filename=file.filename
        )
        
        logger.info(f"Document {file.filename} upload started, processing in background")
        
        return document
        
    except HTTPException as he:
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except:
                pass
        raise he
    except Exception as e:
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except:
                pass
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(500, str(e))


@app.get("/documents/{project_id}")
async def list_documents(project_id: str):
    """List all documents for a project"""
    try:
        response = supabase_client.table("documents").select("*").eq("project_id", project_id).execute()
        return {"documents": response.data}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/documents/{document_id}")
async def delete_document(document_id: str, project_id: str):
    """Delete a document and its chunks"""
    try:
        # Delete chunks first (cascade should handle this, but be explicit)
        supabase_client.table("document_chunks").delete().eq("document_id", document_id).execute()
        
        # Delete document
        supabase_client.table("documents").delete().eq("id", document_id).execute()
        
        logger.info(f"Deleted document {document_id}")
        return {"message": "Document deleted successfully"}
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        raise HTTPException(500, str(e))
