import os
import asyncio
import httpx
from typing import Optional, List
from db.client import supabase_client
from config.settings import settings
from utils.file_parser import FileParser
from utils.text_chunker import TextChunker
from utils.logger import logger


class DocumentProcessor:
    def __init__(self):
        self.client = supabase_client
        self.file_parser = FileParser()
        self.text_chunker = TextChunker(
            chunk_size=settings.CHUNK_SIZE, overlap=settings.CHUNK_OVERLAP
        )

    async def process_document(
        self, document_id: str, project_id: str, file_path: str, filename: str
    ):
        """
        Process uploaded document: extract text, chunk, and send directly to main API.

        OPTIMIZED FLOW (No Supabase document_chunks storage):
        1. Extract text from file
        2. Chunk text
        3. Send chunks directly to main backend via webhook
        4. Main backend generates embeddings and stores in Qdrant
        5. Clean up temp file
        """
        logger.info(f"[{filename}] Starting document processing | ID: {document_id}")

        try:
            # Update status to processing
            await self._update_document_status(document_id, "processing")

            loop = asyncio.get_running_loop()

            # 1. Extract text (Run in thread pool to avoid blocking)
            logger.info(f"[{filename}] Extracting text...")
            await self._update_document_status(
                document_id, "processing", "Extracting text..."
            )

            try:
                text = await loop.run_in_executor(
                    None, self.file_parser.extract_text, file_path
                )
            except Exception as extract_error:
                logger.error(f"[{filename}] Text extraction failed: {extract_error}")
                await self._update_document_status(
                    document_id,
                    "failed",
                    f"Text extraction error: {str(extract_error)}",
                )
                return

            if not text:
                logger.error(f"[{filename}] No text extracted from document")
                await self._update_document_status(
                    document_id,
                    "failed",
                    "Failed to extract text - document may be empty or corrupted",
                )
                return

            logger.info(f"[{filename}] Extracted {len(text)} characters")

            # 2. Chunk text (Run in thread pool to avoid blocking)
            logger.info(f"[{filename}] Chunking text...")
            await self._update_document_status(
                document_id, "processing", "Chunking text..."
            )
            chunks = await loop.run_in_executor(
                None, lambda: self.text_chunker.chunk_text(text)
            )

            if not chunks:
                logger.error(f"[{filename}] No chunks generated from text")
                await self._update_document_status(
                    document_id, "failed", "No chunks generated"
                )
                return

            logger.info(f"[{filename}] Generated {len(chunks)} chunks")

            # 3. Send chunks directly to main API (no Supabase storage)
            await self._update_document_status(
                document_id,
                "processing",
                f"Sending {len(chunks)} chunks for embedding...",
            )
            success = await self._send_chunks_to_main_api(
                document_id, project_id, filename, chunks
            )

            if not success:
                logger.error(f"[{filename}] Failed to send chunks to main API")
                await self._update_document_status(
                    document_id, "failed", "Failed to send chunks to main API"
                )
                return

            # Status will be updated to "completed" by main API after embedding
            logger.info(f"[{filename}] Chunks sent to main API successfully")

        except Exception as e:
            logger.error(f"[{filename}] Processing error: {str(e)}")
            import traceback

            logger.error(f"[{filename}] Traceback: {traceback.format_exc()}")
            await self._update_document_status(document_id, "failed", str(e))

        finally:
            # 5. Clean up temp file (always runs, success or failure)
            self._cleanup_temp_file(file_path)

    def _cleanup_temp_file(self, file_path: str):
        """Remove temporary file after processing"""
        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
                logger.info(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp file {file_path}: {e}")

    async def _update_document_status(
        self, document_id: str, status: str, message: Optional[str] = None
    ):
        """Update document processing status in database"""
        try:
            update_data = {"upload_status": status}
            if status == "completed":
                update_data["error_message"] = None
            elif message:
                update_data["error_message"] = message

            self.client.table("documents").update(update_data).eq(
                "id", document_id
            ).execute()

        except Exception as e:
            logger.error(f"Error updating document status: {str(e)}")

    async def _send_chunks_to_main_api(
        self, document_id: str, project_id: str, filename: str, chunks: List[str]
    ) -> bool:
        """
        Send chunks directly to main API for embedding.
        Includes retry logic with exponential backoff.

        Returns True if successful, False otherwise.
        """
        webhook_url = settings.MAIN_API_WEBHOOK_URL

        payload = {
            "document_id": document_id,
            "project_id": project_id,
            "filename": filename,
            "chunks": chunks,
            "secret": settings.MAIN_API_WEBHOOK_SECRET,
        }

        max_retries = 3
        base_delay = 2.0

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        webhook_url,
                        json=payload,
                        timeout=120.0,  # Longer timeout for large documents
                    )

                    if response.status_code == 200:
                        logger.info(
                            f"Successfully sent chunks to main API for document {document_id}"
                        )
                        return True
                    elif response.status_code >= 500:
                        # Server error, retry
                        logger.warning(
                            f"Main API returned {response.status_code}, retrying..."
                        )
                    else:
                        # Client error, don't retry
                        logger.error(
                            f"Main API webhook failed with {response.status_code}: {response.text}"
                        )
                        return False

            except httpx.TimeoutException:
                logger.warning(f"Webhook timeout (attempt {attempt + 1}/{max_retries})")
            except Exception as e:
                logger.error(
                    f"Webhook error (attempt {attempt + 1}/{max_retries}): {str(e)}"
                )

            # Exponential backoff before retry
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                logger.info(f"Retrying in {delay}s...")
                await asyncio.sleep(delay)

        logger.error(f"Failed to send chunks after {max_retries} attempts")
        return False


document_processor = DocumentProcessor()
