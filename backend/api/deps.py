from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from config.settings import settings
from typing import Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    if payload.get("mgd"):
        # School-created student account: works only while the school is approved,
        # paid up and hasn't switched this account off (cached for a minute).
        from services.institution_service import institutions
        access = await institutions.managed_access(user_id)
        if not access.get("ok"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "school_inactive", "state": access.get("state"),
                        "message": access.get("message") or "Your school's Lumina IQ access is paused."},
            )
    return {"id": user_id, "email": payload.get("email"), "managed": bool(payload.get("mgd"))}

async def get_current_user_with_role(current_user: dict = Depends(get_current_user)):
    from db.client import get_supabase_client
    client = get_supabase_client()
    try:
        response = client.table('user_roles').select('role').eq('user_id', current_user['id']).execute()
        if response.data and len(response.data) > 0:
            current_user['role'] = response.data[0]['role']
        else:
            current_user['role'] = 'handler' # Default role if not found
        return current_user
    except Exception as e:
        # If the table doesn't exist yet or other DB error, fallback gracefully
        current_user['role'] = 'handler'
        return current_user

async def require_owner(current_user: dict = Depends(get_current_user_with_role)):
    if current_user.get('role') != 'owner':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action. Owner role required."
        )
    return current_user

async def require_admin(current_user: dict = Depends(get_current_user_with_role)):
    if current_user.get('role') not in ['owner', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action. Admin or Owner role required."
        )
    return current_user
