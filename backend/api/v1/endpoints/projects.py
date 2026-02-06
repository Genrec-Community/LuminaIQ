from fastapi import APIRouter, HTTPException, Depends, status
from services.project_service import project_service
from models.schemas import ProjectCreate, ProjectResponse
from typing import List, Any
from api.deps import get_current_user

router = APIRouter()

@router.post("/", response_model=ProjectResponse)
async def create_project(
    project_in: ProjectCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new project.
    """
    try:
        project = await project_service.create_project(user_id=current_user["id"], name=project_in.name)
        return project
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[Any]) 
async def get_projects(
    current_user: dict = Depends(get_current_user)
):
    """
    Get all projects for the current user.
    """
    try:
        projects = await project_service.get_projects(user_id=current_user["id"])
        return projects
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get project details.
    """
    try:
        project = await project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Authorization Check: Ensure project belongs to user
        if project["user_id"] != current_user["id"]:
             raise HTTPException(status_code=403, detail="Not authorized to access this project")
             
        return project
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a project.
    """
    try:
        project = await project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        if project["user_id"] != current_user["id"]:
             raise HTTPException(status_code=403, detail="Not authorized to delete this project")
             
        success = await project_service.delete_project(project_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete project")
            
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))