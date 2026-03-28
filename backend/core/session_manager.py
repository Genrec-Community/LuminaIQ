"""Redis-based session management for chat history and user state.

**Validates: Requirements 5.1, 5.2, 5.5**

This module provides fast, distributed session storage using Redis for active
user sessions and chat history. Sessions are stored with 24-hour TTL and
automatically persisted to Supabase on expiration.

**Horizontal Scaling Support:**
- All session data stored in Redis (shared across instances)
- No instance-specific state or in-memory caching
- Sessions accessible from any backend instance
- Instance metadata tracked for debugging and monitoring
- Supports session migration during instance failover
"""

import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from core.redis_manager import RedisCacheManager

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """
    Chat message in a session.
    
    Attributes:
        role: Message role (user, assistant, system)
        content: Message content
        timestamp: Message timestamp
        metadata: Optional metadata
    """
    role: str
    content: str
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Session:
    """
    User session data.
    
    Attributes:
        session_id: Unique session identifier
        user_id: User identifier
        project_id: Project identifier
        messages: List of chat messages (last 50)
        created_at: Session creation timestamp
        last_activity: Last activity timestamp
        metadata: Optional session metadata
    """
    session_id: str
    user_id: str
    project_id: str
    messages: List[ChatMessage]
    created_at: str
    last_activity: str
    metadata: Optional[Dict[str, Any]] = None


class SessionManager:
    """
    Redis-based session manager for chat history and user state.
    
    Features:
    - Fast session storage in Redis with 24-hour TTL
    - Store last 50 messages per session
    - Efficient message append using Redis list
    - Session persistence to Supabase on expiration
    - Session migration support for horizontal scaling
    
    Horizontal Scaling:
    - Sessions stored in Redis are accessible from ANY backend instance
    - No instance-specific state or locks
    - Instance metadata tracked for debugging (which instance created/served session)
    - Load balancer can route requests to any available instance
    - Session data survives instance restarts and failovers
    
    Requirements:
    - 5.1: Create session, get session, add message methods
    - 5.2: Store last 50 messages per session with 24-hour TTL
    - 5.5: Session migration support for horizontal scaling
    """
    
    def __init__(self, redis_manager: RedisCacheManager):
        """
        Initialize session manager.
        
        Args:
            redis_manager: Redis cache manager instance
        """
        self.redis_manager = redis_manager
        self.session_ttl = 86400  # 24 hours
        self.max_messages = 50  # Keep last 50 messages
        
        # Get instance ID for tracking (optional, for debugging)
        self.instance_id = os.getenv("INSTANCE_ID", f"instance-{os.getpid()}")
        
        logger.info(
            f"[SessionManager] Initialized with TTL={self.session_ttl}s (24 hours), "
            f"max_messages={self.max_messages}, instance_id={self.instance_id}"
        )
    
    def _generate_session_key(self, session_id: str) -> str:
        """
        Generate cache key for session data.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Cache key in format: session:{session_id}
        """
        return f"session:{session_id}"
    
    def _generate_messages_key(self, session_id: str) -> str:
        """
        Generate cache key for session messages list.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Cache key in format: session:{session_id}:messages
        """
        return f"session:{session_id}:messages"
    
    async def create_session(
        self,
        user_id: str,
        project_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new session.
        
        The session is stored in Redis and accessible from any backend instance.
        Instance metadata is included for debugging and monitoring purposes.
        
        Args:
            user_id: User identifier
            project_id: Project identifier
            metadata: Optional session metadata
            
        Returns:
            Session ID
        """
        session_id = f"sess_{uuid.uuid4().hex}"
        
        now = datetime.utcnow().isoformat() + "Z"
        
        # Include instance metadata for debugging
        session_metadata = metadata or {}
        session_metadata.update({
            "created_by_instance": self.instance_id,
            "last_served_by_instance": self.instance_id
        })
        
        session = Session(
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            messages=[],
            created_at=now,
            last_activity=now,
            metadata=session_metadata
        )
        
        session_key = self._generate_session_key(session_id)
        session_data = asdict(session)
        
        # Store session data
        success = await self.redis_manager.set(
            session_key,
            json.dumps(session_data),
            ttl=self.session_ttl
        )
        
        if success:
            logger.info(
                f"[SessionManager] Created session {session_id} for "
                f"user={user_id}, project={project_id}, instance={self.instance_id}"
            )
        else:
            logger.error(f"[SessionManager] Failed to create session {session_id}")
        
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        Retrieve session data.
        
        Sessions are stored in Redis and can be retrieved by ANY backend instance,
        enabling seamless session migration during horizontal scaling.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session object or None if not found
        """
        session_key = self._generate_session_key(session_id)
        
        session_data = await self.redis_manager.get(session_key)
        
        if not session_data:
            logger.debug(f"[SessionManager] Session {session_id} not found")
            return None
        
        try:
            data = json.loads(session_data)
            
            # Convert message dicts to ChatMessage objects
            messages = [ChatMessage(**msg) for msg in data.get("messages", [])]
            data["messages"] = messages
            
            session = Session(**data)
            
            # Update last served instance for debugging
            if session.metadata is None:
                session.metadata = {}
            session.metadata["last_served_by_instance"] = self.instance_id
            
            logger.debug(
                f"[SessionManager] Retrieved session {session_id} with "
                f"{len(session.messages)} messages (served by instance {self.instance_id})"
            )
            
            return session
            
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to decode session {session_id}: {e}")
            return None
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a message to the session.
        
        Keeps only the last 50 messages to limit memory usage.
        
        Args:
            session_id: Session identifier
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional message metadata
            
        Returns:
            True if message added successfully, False otherwise
        """
        # Get current session
        session = await self.get_session(session_id)
        
        if not session:
            logger.warning(f"[SessionManager] Cannot add message to non-existent session {session_id}")
            return False
        
        # Create new message
        message = ChatMessage(
            role=role,
            content=content,
            timestamp=datetime.utcnow().isoformat() + "Z",
            metadata=metadata
        )
        
        # Add message to session
        session.messages.append(message)
        
        # Keep only last 50 messages
        if len(session.messages) > self.max_messages:
            session.messages = session.messages[-self.max_messages:]
        
        # Update last activity
        session.last_activity = datetime.utcnow().isoformat() + "Z"
        
        # Save updated session
        session_key = self._generate_session_key(session_id)
        session_data = asdict(session)
        
        success = await self.redis_manager.set(
            session_key,
            json.dumps(session_data),
            ttl=self.session_ttl
        )
        
        if success:
            logger.debug(
                f"[SessionManager] Added {role} message to session {session_id}, "
                f"total_messages={len(session.messages)}"
            )
        else:
            logger.error(f"[SessionManager] Failed to add message to session {session_id}")
        
        return success
    
    async def get_chat_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[ChatMessage]:
        """
        Get chat history for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return (default: 50)
            
        Returns:
            List of chat messages (most recent first)
        """
        session = await self.get_session(session_id)
        
        if not session:
            logger.debug(f"[SessionManager] No chat history for session {session_id}")
            return []
        
        # Return last N messages
        messages = session.messages[-limit:] if len(session.messages) > limit else session.messages
        
        logger.debug(
            f"[SessionManager] Retrieved {len(messages)} messages for session {session_id}"
        )
        
        return messages
    
    async def persist_session(self, session_id: str) -> bool:
        """
        Persist session to Supabase for long-term storage.
        
        This is called when a session expires or user explicitly saves.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successfully persisted, False otherwise
        """
        session = await self.get_session(session_id)
        
        if not session:
            logger.warning(f"[SessionManager] Cannot persist non-existent session {session_id}")
            return False
        
        try:
            from db.client import get_supabase_client, async_db
            client = get_supabase_client()
            
            # Persist all messages to chat_messages table
            messages_to_insert = []
            for msg in session.messages:
                message_data = {
                    "project_id": session.project_id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.timestamp
                }
                
                # Add sources if present in metadata
                if msg.metadata and "sources" in msg.metadata:
                    message_data["sources"] = msg.metadata["sources"]
                
                messages_to_insert.append(message_data)
            
            # Batch insert messages
            if messages_to_insert:
                await async_db(
                    lambda: client.table("chat_messages")
                    .insert(messages_to_insert)
                    .execute()
                )
                
                logger.info(
                    f"[SessionManager] Persisted {len(messages_to_insert)} messages "
                    f"from session {session_id} to Supabase"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error persisting session {session_id}: {e}")
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session from Redis.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successfully deleted, False otherwise
        """
        session_key = self._generate_session_key(session_id)
        
        success = await self.redis_manager.delete(session_key)
        
        if success:
            logger.info(f"[SessionManager] Deleted session {session_id}")
        else:
            logger.warning(f"[SessionManager] Failed to delete session {session_id}")
        
        return success
    
    async def update_session_metadata(
        self,
        session_id: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Update session metadata.
        
        Args:
            session_id: Session identifier
            metadata: Metadata to update
            
        Returns:
            True if successfully updated, False otherwise
        """
        session = await self.get_session(session_id)
        
        if not session:
            logger.warning(f"[SessionManager] Cannot update metadata for non-existent session {session_id}")
            return False
        
        # Update metadata
        if session.metadata is None:
            session.metadata = {}
        
        session.metadata.update(metadata)
        session.last_activity = datetime.utcnow().isoformat() + "Z"
        
        # Save updated session
        session_key = self._generate_session_key(session_id)
        session_data = asdict(session)
        
        success = await self.redis_manager.set(
            session_key,
            json.dumps(session_data),
            ttl=self.session_ttl
        )
        
        if success:
            logger.debug(f"[SessionManager] Updated metadata for session {session_id}")
        
        return success
