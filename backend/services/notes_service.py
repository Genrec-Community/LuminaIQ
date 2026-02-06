from typing import Dict, Any, List
from supabase import create_client, Client
from config.settings import settings
from utils.logger import logger
from uuid import uuid4
from datetime import datetime
from services.llm_service import llm_service
from services.embedding_service import embedding_service
from services.qdrant_service import qdrant_service

class NotesService:
    def __init__(self):
        self.client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY
        )
    
    async def get_notes(self, project_id: str, user_id: str) -> Dict[str, Any]:
        """Get notes for a project"""
        try:
            response = self.client.table("notes").select("*").eq(
                "project_id", project_id
            ).eq("user_id", user_id).execute()
            
            if response.data:
                note = response.data[0]
                return {
                    "id": note["id"],
                    "project_id": note["project_id"],
                    "user_id": note["user_id"],
                    "content": note["content"],
                    "created_at": note["created_at"],
                    "updated_at": note["updated_at"]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting notes: {str(e)}")
            raise
    
    async def create_or_update_notes(
        self,
        project_id: str,
        user_id: str,
        content: str
    ) -> Dict[str, Any]:
        """Create or update notes for a project"""
        try:
            # Check if notes exist
            existing = await self.get_notes(project_id, user_id)
            
            if existing:
                # Update existing notes
                response = self.client.table("notes").update({
                    "content": content,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", existing["id"]).execute()
                
                logger.info(f"Updated notes for project {project_id}")
            else:
                # Create new notes
                note_id = str(uuid4())
                response = self.client.table("notes").insert({
                    "id": note_id,
                    "project_id": project_id,
                    "user_id": user_id,
                    "content": content
                }).execute()
                
                logger.info(f"Created notes for project {project_id}")
            
            return response.data[0] if response.data else {}
            
        except Exception as e:
            logger.error(f"Error creating/updating notes: {str(e)}")
            raise

    async def generate_notes(
        self,
        project_id: str,
        note_type: str,
        topic: str = None,
        selected_documents: List[str] = None
    ) -> str:
        """Generate notes using AI"""
        try:
            logger.info(f"Generating notes ({note_type}) for project {project_id}, topic: {topic}")
            
            # 1. Retrieve Content
            queries = []
            if topic:
                # If topic is provided, prioritize it
                queries = [topic, f"{note_type} of {topic}"]
            elif "Summary" in note_type:
                queries = ["overview of the document", "main concepts and themes", "conclusion and results"]
            elif "Key Points" in note_type:
                queries = ["important definitions", "key takeaways", "critical points"]
            else:
                queries = [note_type]
            
            collection_name = f"project_{project_id}"
            all_hits = []
            seen_texts = set()
            
            for q in queries:
                embedding = await embedding_service.generate_embedding(q)
                results = await qdrant_service.search(
                    collection_name=collection_name,
                    query_vector=embedding,
                    limit=10, # Fetch robust amount
                    filter_conditions={"document_ids": selected_documents} if selected_documents else None
                )
                for hit in results:
                    if hit["text"] not in seen_texts:
                        all_hits.append(hit)
                        seen_texts.add(hit["text"])
            
            if not all_hits:
                return "No content found to generate notes."
                
            # Combine content (limit to reasonable context window)
            context = "\n\n".join([hit["text"] for hit in all_hits[:20]])
            
            # 2. Generate Note
            prompt = f"""Generate a **{note_type}** based on the following content.
            
Content:
{context}

Requirements:
- Use clear, professional Markdown formatting.
- Use headers, bullet points, and bold text for readability.
- Be comprehensive but concise.
- Structure it as a study guide or note set.

Respond ONLY with the Markdown content."""

            messages = [{"role": "user", "content": prompt}]
            response = await llm_service.chat_completion(messages, temperature=0.5, max_tokens=2500)
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating notes: {str(e)}")
            raise

notes_service = NotesService()
