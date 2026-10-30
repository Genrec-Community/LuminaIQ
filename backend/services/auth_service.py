from datetime import datetime, timedelta
import re
import time
import asyncio
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from db.client import get_supabase_client, async_db
from config.settings import settings
from utils.logger import logger
from services import school_accounts


class SchoolInactive(Exception):
    """A school-created account whose school isn't working (or that was switched off)."""

    def __init__(self, access: Dict[str, Any]):
        super().__init__(access.get("message") or "Your school's Lumina IQ access is paused.")
        self.access = access

# Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def __init__(self):
        # Use the singleton client instead of creating a new one
        self.client = get_supabase_client()

    def verify_password(self, plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password):
        return pwd_context.hash(password)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt

    async def signup(self, email: str, password: str, full_name: str) -> Dict[str, Any]:
        """Register a new user (via Supabase Auth) with retry logic"""
        try:
            if school_accounts.is_school_login(email):
                raise ValueError(
                    f"@{school_accounts.login_domain()} IDs are created by schools. "
                    "Sign in with the ID and password your school gave you."
                )
            # Validate password strength
            if len(password) < 8:
                raise ValueError("Password must be at least 8 characters long")
            if not re.search(r"[a-z]", password):
                raise ValueError("Password must contain at least one lowercase letter")
            if not re.search(r"[A-Z]", password):
                raise ValueError("Password must contain at least one uppercase letter")
            if not re.search(r"\d", password):
                raise ValueError("Password must contain at least one digit")
            if not re.search(r"[\W_]", password):
                raise ValueError("Password must contain at least one symbol")

            # Retry logic for transient failures
            max_retries = 3
            retry_delay = 1  # seconds
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Signup attempt {attempt + 1}/{max_retries} for: {email}")
                    
                    # REST sign-up (triggers the confirmation email if enabled in Supabase).
                    # Not client.auth.sign_up: with confirmations off it signs the shared
                    # service-role client in as this user.
                    created = await school_accounts.rest_signup(email, password, {"full_name": full_name})
                    if created.get("id"):
                        logger.info(f"User signed up successfully: {email}")
                        return {
                            "id": created["id"],
                            "email": created.get("email") or email,
                            "created_at": created.get("created_at"),
                            "full_name": full_name
                        }
                    else:
                        raise Exception("User registration failed - no user returned")

                except school_accounts.AuthUnavailable as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Signup could not reach Supabase Auth (attempt {attempt + 1}), retrying...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    raise Exception("Authentication service is temporarily unavailable. Please try again in a few moments.")
                except Exception as e:
                    error_msg = str(e).lower()
                    last_error = e
                    
                    # Check if it's a timeout or network error
                    if any(keyword in error_msg for keyword in ['timeout', 'timed out', 'connection', 'network']):
                        if attempt < max_retries - 1:
                            logger.warning(f"Signup timeout on attempt {attempt + 1}, retrying in {retry_delay}s...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                            continue
                        else:
                            logger.error(f"Signup failed after {max_retries} attempts: {str(e)}")
                            raise Exception("Authentication service is temporarily unavailable. Please try again in a few moments.")
                    else:
                        # Non-timeout error, don't retry
                        raise
            
            # If we get here, all retries failed
            raise last_error if last_error else Exception("Signup failed")
                
        except Exception as e:
            logger.error(f"Signup error: {str(e)}")
            raise
    
    async def issue_session(self, user_id: str, email: str, full_name: str) -> Dict[str, Any]:
        """Our JWT for a verified user. School-created accounts are checked against their school first."""
        from services.institution_service import institutions

        info = {"managed": False, "must_change_password": False}
        claims = {"sub": user_id, "email": email, "full_name": full_name}
        try:
            info = await institutions.account_info(user_id)
        except Exception as e:
            logger.warning(f"School lookup failed at sign-in for {user_id}: {e}")
        if info.get("managed"):
            institutions.forget(user_id=user_id)
            access = await institutions.managed_access(user_id)
            if not access.get("ok"):
                raise SchoolInactive(access)
            claims["mgd"] = access.get("institution_id") or True
        access_token = self.create_access_token(
            data=claims, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user_id, "email": email, "full_name": full_name,
                "managed": bool(info.get("managed")),
                "must_change_password": bool(info.get("must_change_password")),
                "login_id": info.get("login_id"),
            },
        }

    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Check the password with Supabase Auth's REST endpoint and return our JWT.
        (Not client.auth.sign_in_with_password: that would switch the shared
        service-role client to this user's token for every later query.)
        """
        email = (email or "").strip()
        if "@" not in email and email:
            # Students may type just the part before @ of their school ID
            email = f"{email.lower()}@{school_accounts.login_domain()}"
        logger.info(f"Attempting login for: {email}")
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                user = await school_accounts.password_grant(email, password)
                break
            except school_accounts.AuthUnavailable as e:
                last_error = e
                logger.warning(f"Login attempt {attempt + 1} could not reach Supabase Auth: {e}")
                await asyncio.sleep(2 ** attempt)
        else:
            raise Exception("Authentication service is temporarily unavailable. Please try again in a few moments.") from last_error
        full_name = (user.get("user_metadata") or {}).get("full_name", "")
        session = await self.issue_session(user["id"], user.get("email") or email, full_name)
        logger.info(f"User logged in successfully: {email}")
        return session

    async def change_password(self, user_id: str, current_password: str, new_password: str) -> None:
        """Change your own password (students included). Needs the current one."""
        from services.institution_service import institutions

        res = await async_db(lambda: self.client.auth.admin.get_user_by_id(user_id))
        email = res.user.email if res and res.user else None
        if not email:
            raise ValueError("This account can't use a password.")
        try:
            await school_accounts.password_grant(email, current_password)
        except school_accounts.InvalidCredentials:
            raise ValueError("Your current password is wrong.")
        if current_password == new_password:
            raise ValueError("Choose a password different from the current one.")
        problem = school_accounts.password_problem(new_password)
        if problem:
            raise ValueError(problem)
        await async_db(lambda: self.client.auth.admin.update_user_by_id(user_id, {"password": new_password}))
        try:
            await institutions.mark_password_changed(user_id)
        except Exception as e:
            logger.warning(f"must_change_password not cleared for {user_id}: {e}")
        logger.info(f"Password changed for {user_id}")

    async def exchange_supabase_token(self, supabase_token: str) -> Dict[str, Any]:
        """Exchange Supabase OAuth or OTP token for App JWT"""
        try:
            user = self.client.auth.get_user(supabase_token)
            if not user or not user.user:
                raise Exception("Invalid Supabase Token")
            
            u = user.user
            email = u.email
            full_name = u.user_metadata.get("full_name", "") or u.user_metadata.get("name", "")
            
            return await self.issue_session(u.id, email, full_name)
        except Exception as e:
            logger.error(f"Token Exchange Error: {e}")
            raise

    async def create_handler(self, email: str, password: str, full_name: str) -> Dict[str, Any]:
        """Create a new handler user directly (Admin function)"""
        try:
            # Validate password strength
            if len(password) < 8:
                raise ValueError("Password must be at least 8 characters long")
            
            logger.info(f"Admin creating handler: {email}")
            
            # Use Supabase Admin API to create user (requires SERVICE_ROLE key which is default in client)
            # This bypasses email confirmation requirements
            response = self.client.auth.admin.create_user({
                "email": email,
                "password": password,
                "user_metadata": {"full_name": full_name},
                "email_confirm": True
            })
            
            if response.user:
                # Add to user_roles table
                (await async_db(lambda: self.client.table('user_roles').insert({
                    'user_id': response.user.id,
                    'role': 'handler'
                }).execute()))
                
                logger.info(f"Handler created successfully: {email}")
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "full_name": full_name,
                    "role": "handler"
                }
            else:
                raise Exception("Failed to create user - no user returned")
                
        except Exception as e:
            logger.error(f"Create handler error: {str(e)}")
            raise

auth_service = AuthService()