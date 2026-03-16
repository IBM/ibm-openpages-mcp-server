"""
JWT Token Utilities

Provides functions to decode and extract information from JWT tokens
for logging and user identification purposes.
"""

import jwt
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def decode_jwt_token(token: str, verify: bool = False) -> Optional[Dict[str, Any]]:
    """
    Decode a JWT token without verification (for extracting claims)
    
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
        
        # Decode without verification (we just need the user ID for logging)
        decoded = jwt.decode(token, options={"verify_signature": verify})
        return decoded
    except jwt.DecodeError as e:
        logger.debug(f"Failed to decode JWT token (not a JWT): {e}")
        return None
    except Exception as e:
        logger.warning(f"Failed to decode JWT token: {e}")
        return None


def extract_user_id_from_token(token: str) -> Optional[str]:
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
    
    decoded = decode_jwt_token(token)
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
                logger.debug(f"Extracted user ID from JWT token: {user_id}")
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