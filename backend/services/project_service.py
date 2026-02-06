from db.client import supabase_client
from config.settings import settings
from utils.logger import logger
from typing import List, Dict, Any, Optional
from uuid import uuid4

class ProjectService:
    def __init__(self):
        self.client = supabase_client
    
    async def create_project(self, user_id: str, name: str) -> Dict[str, Any]:
        """Create a new project"""
        try:
            response = self.client.table("projects").insert({
                "user_id": user_id,
                "name": name
            }).execute()
            
            if response.data:
                logger.info(f"Created project: {name}")
                return response.data[0]
            else:
                raise Exception("Failed to create project")
                
        except Exception as e:
            logger.error(f"Error creating project: {str(e)}")
            raise

    async def get_projects(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all projects for a user"""
        try:
            response = self.client.table("projects").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
            
            # Enrich with doc count if possible (separate query or join?)
            # Supabase JS client doesn't support deep joins easily in one go like raw SQL for counts usually.
            # We'll fetch basic info first.
            projects = response.data
            
            # Fetch doc counts
            for p in projects:
                # This is N+1 query, but okay for small scale prototype. 
                # Better way: use a postgres function or view.
                doc_res = self.client.table("documents").select("id", count="exact").eq("project_id", p["id"]).execute()
                p["docs"] = doc_res.count
                
            return projects
        except Exception as e:
            logger.error(f"Error getting projects: {str(e)}")
            return []

    async def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific project"""
        try:
            response = self.client.table("projects").select("*").eq("id", project_id).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting project: {str(e)}")
            return None

    async def delete_project(self, project_id: str) -> bool:
        """Delete a project"""
        try:
            self.client.table("projects").delete().eq("id", project_id).execute()
            logger.info(f"Deleted project: {project_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting project: {str(e)}")
            return False

project_service = ProjectService()