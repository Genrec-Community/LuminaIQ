from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from config.settings import settings
from typing import Optional
from db.client import async_db, get_supabase_client

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return {"id": user_id, "email": payload.get("email")}
    except JWTError:
        raise credentials_exception


async def require_project_owner(
    project_id: str,
    current_user: dict,
    client=None,
):
    database = client or get_supabase_client()
    response = await async_db(
        lambda: database.table("projects")
        .select("id, user_id")
        .eq("id", project_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Project not found")
    if response.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access this project",
        )
    return response.data[0]


async def require_document_in_project(
    document_id: str,
    project_id: str,
    client=None,
):
    database = client or get_supabase_client()
    response = await async_db(
        lambda: database.table("documents")
        .select("id, project_id")
        .eq("id", document_id)
        .eq("project_id", project_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Document not found in project",
        )
    return response.data[0]


async def require_document_owner(
    document_id: str,
    current_user: dict,
    client=None,
):
    database = client or get_supabase_client()
    response = await async_db(
        lambda: database.table("documents")
        .select("id, project_id")
        .eq("id", document_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Document not found")
    document = response.data[0]
    await require_project_owner(
        document["project_id"],
        current_user,
        client=database,
    )
    return document
