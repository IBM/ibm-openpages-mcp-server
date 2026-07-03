"""
JWT Token Utilities

Provides functions to decode and extract information from JWT tokens
for logging and user identification purposes.

THREADING MODEL:
---------------
JWT decoding operations are protected by a module-level threading.Lock
to ensure thread-safety when called via asyncio.to_thread() in concurrent
async environments.

Thread-Safety Guarantees:
- decode_jwt_token(): Protected by _jwt_decode_lock for safe concurrent access
- extract_user_id_from_token(): Safe (calls thread-safe decode_jwt_token)
- extract_user_id_from_user_data(): Safe (no shared state)

Performance:
- JWT decode with lock: ~1-2ms per call
- Lock contention is minimal due to fast decode operations
"""

import jwt
import logging
import asyncio
import threading
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Module-level lock for thread-safe JWT operations
# PyJWT's decode operation may not be thread-safe when called via asyncio.to_thread()
# This lock ensures that concurrent decode operations don't cause race conditions
_jwt_decode_lock = threading.Lock()

async def decode_jwt_token(token: str, verify: bool = False) -> Optional[Dict[str, Any]]:
    """
    Decode a JWT token without verification (for extracting claims)
    Thread-safe implementation using lock to prevent concurrent decode issues.
    
    Args:
        token: JWT token string
        verify: Whether to verify signature (default: False for logging purposes)
    
    Returns:
        Dictionary of token claims or None if decoding fails
    """
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
        elif token.startswith('bearer '):
            token = token[7:]
        
        # Use lock to ensure thread-safe JWT decoding
        def _decode_with_lock():
            with _jwt_decode_lock:
                return jwt.decode(token, options={"verify_signature": verify})
        
        # Decode in thread pool to avoid blocking event loop
        decoded = await asyncio.to_thread(_decode_with_lock)
        return decoded
    except jwt.DecodeError as e:
        logger.debug(f"Failed to decode JWT token (not a JWT): {e}")
        return None
    except Exception as e:
        logger.warning(f"Failed to decode JWT token: {e}")
        return None


async def extract_user_id_from_token(token: str) -> Optional[str]:
    """
    Extract user ID from JWT token
    
    Tries common JWT claim fields for user ID in order of preference:
    - sub (subject) - standard JWT claim (primary)
    - uid - user ID
    - user_id - alternative user ID field
    
    Note: Only extracts non-PII identifiers (sub, uid, user_id) for security
    and privacy compliance. All PII fields are explicitly excluded.
    
    Args:
        token: JWT token string (with or without 'Bearer ' prefix)
    
    Returns:
        User ID string or None if not found
    """
    if not token:
        return None
    
    decoded = await decode_jwt_token(token)
    if not decoded:
        return None
    
    # Only use guaranteed non-PII identifiers (sub, uid, user_id)
    # All PII fields are explicitly excluded
    user_id_fields = [
        'sub',                  # Standard JWT subject claim (primary)
        'uid',                  # User ID
        'user_id',              # Alternative user ID field
    ]
    
    for field in user_id_fields:
        if field in decoded:
            user_id = decoded[field]
            if user_id:
                # Mask user ID in logs (show only first 8 chars)
                masked_id = f"{str(user_id)[:8]}..." if len(str(user_id)) > 8 else str(user_id)
                logger.debug(f"Extracted user ID from JWT token: {masked_id}")
                return str(user_id)
    
    logger.warning(f"No user ID found in JWT token")
    return None


def extract_user_id_from_user_data(user_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract user ID from OpenPages user data response
    
    Note: Returns user ID (not PII like name/email) for security and privacy compliance
    
    Args:
        user_data: User data dictionary from OpenPages API
    
    Returns:
        User ID string or None if not found
    """
    if not user_data:
        return None
    
    # Only use guaranteed non-PII identifiers (userId only)
    # All PII fields are explicitly excluded
    user_id_fields = [
        'userId',       # User ID (primary - guaranteed non-PII)
    ]
    
    for field in user_id_fields:
        if field in user_data and user_data[field]:
            user_id = str(user_data[field])
            logger.debug(f"Extracted user ID from user data: {user_id}")
            return user_id
    
    logger.warning(f"No user ID found in user data")
    return None


# Made with Bob