"""
Session Management Middleware
"""

import asyncio
import secrets
import time
from typing import Dict


class SessionManager:
    """Simple in-memory session manager"""
    
    def __init__(self, session_timeout: int = 3600):
        """
        Initialize session manager
        
        Args:
            session_timeout: Session timeout in seconds
        """
        self.session_timeout = session_timeout
        self.sessions: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
    
    async def create_session(self, user_id: int) -> str:
        """
        Create a new session for user
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Session ID
        """
        async with self._lock:
            session_id = secrets.token_urlsafe(32)
            self.sessions[session_id] = {
                'user_id': user_id,
                'created_at': time.time(),
                'last_accessed': time.time()
            }
            return session_id
    
    async def validate_session(self, session_id: str, user_id: int) -> bool:
        """
        Validate session
        
        Args:
            session_id: Session ID to validate
            user_id: Expected user ID
            
        Returns:
            True if session is valid, False otherwise
        """
        async with self._lock:
            if session_id not in self.sessions:
                return False
            
            session = self.sessions[session_id]
            current_time = time.time()
            
            # Check if session expired
            if current_time - session['last_accessed'] > self.session_timeout:
                del self.sessions[session_id]
                return False
            
            # Check if user matches
            if session['user_id'] != user_id:
                return False
            
            # Update last accessed time
            session['last_accessed'] = current_time
            return True
    
    async def expire_session(self, session_id: str) -> None:
        """Expire a session"""
        async with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
    
    async def cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions"""
        async with self._lock:
            current_time = time.time()
            expired_sessions = [
                session_id for session_id, session in self.sessions.items()
                if current_time - session['last_accessed'] > self.session_timeout
            ]
            
            for session_id in expired_sessions:
                del self.sessions[session_id]
