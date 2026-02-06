from datetime import datetime, timedelta
import re
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from db.client import supabase_client
from config.settings import settings
from utils.logger import logger

# Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def __init__(self):
        # Use the singleton client instead of creating a new one
        self.client = supabase_client

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
        """Register a new user (via Supabase Auth)"""
        try:
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

            # Use Standard Sign Up (triggers confirmation email if enabled in Supabase)
            response = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {"full_name": full_name}
                }
            })
            
            if response.user:
                logger.info(f"User signed up: {email}")
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "created_at": response.user.created_at,
                    "full_name": full_name
                }
            else:
                raise Exception("User registration failed")
                
        except Exception as e:
            logger.error(f"Signup error: {str(e)}")
            raise
    
    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """Login user and return our custom JWT"""
        try:
            logger.info(f"Attempting login for: {email}")
            # Authenticate with Supabase to verify credentials
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            logger.info(f"Supabase response: {response}")

            if response.user:
                # Retrieve full_name from metadata
                full_name = response.user.user_metadata.get("full_name", "")
                logger.info(f"User found: {response.user.id}, full_name: {full_name}")

                # Generate OUR access token
                access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
                access_token = self.create_access_token(
                    data={"sub": response.user.id, "email": email, "full_name": full_name},
                    expires_delta=access_token_expires
                )

                logger.info(f"User logged in successfully: {email}")
                return {
                    "access_token": access_token,
                    "token_type": "bearer",
                    "user": {
                        "id": response.user.id,
                        "email": response.user.email,
                        "full_name": full_name
                    }
                }
            else:
                logger.error("No user in response")
                raise Exception("Invalid credentials")

        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            raise

    async def login_with_google(self, supabase_token: str) -> Dict[str, Any]:
        """Exchange Supabase OAuth token for App JWT"""
        try:
            user = self.client.auth.get_user(supabase_token)
            if not user or not user.user:
                raise Exception("Invalid Google Token")
            
            u = user.user
            email = u.email
            full_name = u.user_metadata.get("full_name", "") or u.user_metadata.get("name", "")
            
            # Generate Custom JWT
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = self.create_access_token(
                data={"sub": u.id, "email": email, "full_name": full_name},
                expires_delta=access_token_expires
            )
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": u.id,
                    "email": email,
                    "full_name": full_name
                }
            }
        except Exception as e:
            logger.error(f"Google Login Error: {e}")
            raise

auth_service = AuthService()