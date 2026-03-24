"""
Claude Code OAuth Authentication Utility

Reads and manages Claude Code OAuth tokens from ~/.claude/.credentials.json
"""
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
import requests

from backend.security import encrypt_data, decrypt_data


# Claude Code OAuth endpoints
CLAUDE_AUTHORIZE_URL = "https://claude.ai/oauth/authorize"
CLAUDE_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
CLAUDE_PROFILE_URL = "https://api.anthropic.com/api/oauth/profile"

# Claude Code CLI client ID
CLAUDE_CODE_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"

# Credentials file path
CREDENTIALS_FILE = Path.home() / ".claude" / ".credentials.json"


def get_claude_code_credentials() -> Optional[Dict[str, Any]]:
    """
    Read Claude Code credentials from ~/.claude/.credentials.json
    
    Returns:
        Dict with accessToken, refreshToken, expiresAt, etc. or None if not found
    """
    if not CREDENTIALS_FILE.exists():
        return None
    
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            data = json.load(f)
        
        return data.get('claudeAiOauth')
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading Claude Code credentials: {e}")
        return None


def is_token_expired(expires_at_ms: int) -> bool:
    """
    Check if token is expired (expires_at is in milliseconds since epoch)
    """
    expires_at_sec = expires_at_ms / 1000
    expires_datetime = datetime.fromtimestamp(expires_at_sec, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    
    # Consider expired if less than 5 minutes remaining
    buffer_seconds = 300  # 5 minutes
    return (expires_datetime.timestamp() - buffer_seconds) < now.timestamp()


def refresh_claude_code_token(refresh_token: str) -> Tuple[Optional[str], Optional[str], Optional[int], Optional[str]]:
    """
    Refresh Claude Code OAuth token using refresh token
    
    Returns:
        (access_token, refresh_token, expires_at_ms, subscription_type) or (None, None, None, error)
    """
    try:
        response = requests.post(
            CLAUDE_TOKEN_URL,
            json={
                "grant_type": "refresh_token",
                "client_id": CLAUDE_CODE_CLIENT_ID,
                "refresh_token": refresh_token
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"Token refresh failed: {response.status_code} - {response.text}")
            return None, None, None, f"Refresh failed: {response.status_code}"
        
        data = response.json()
        
        access_token = data.get('access_token')
        new_refresh_token = data.get('refresh_token', refresh_token)  # May be rotated
        expires_in = data.get('expires_in', 3600)  # Seconds
        expires_at_ms = int((datetime.now(timezone.utc).timestamp() + expires_in) * 1000)
        
        # Get subscription type from profile
        subscription_type = "unknown"
        try:
            profile_response = requests.get(
                CLAUDE_PROFILE_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10
            )
            if profile_response.status_code == 200:
                profile_data = profile_response.json()
                subscription_type = profile_data.get('subscriptionType', 'unknown')
        except:
            pass
        
        return access_token, new_refresh_token, expires_at_ms, subscription_type
        
    except Exception as e:
        print(f"Token refresh error: {e}")
        return None, None, None, str(e)


def import_claude_code_credentials() -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Import Claude Code credentials from CLI
    
    Returns:
        (success, error_message, token_info)
    """
    credentials = get_claude_code_credentials()
    
    if not credentials:
        return False, "Claude Code credentials not found. Please run 'claude auth login' first.", None
    
    access_token = credentials.get('accessToken')
    refresh_token = credentials.get('refreshToken')
    expires_at = credentials.get('expiresAt')
    subscription_type = credentials.get('subscriptionType', 'unknown')
    
    if not access_token or not refresh_token:
        return False, "Invalid credentials format", None
    
    # Check if token is expired
    if expires_at and is_token_expired(expires_at):
        # Try to refresh
        print("Token expired, attempting refresh...")
        new_access, new_refresh, new_expires, sub_type = refresh_claude_code_token(refresh_token)
        
        if new_access:
            access_token = new_access
            refresh_token = new_refresh
            expires_at = new_expires
            subscription_type = sub_type
        else:
            return False, "Token expired and refresh failed. Please run 'claude auth login' again.", None
    
    token_info = {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_at': expires_at,
        'subscription_type': subscription_type,
        'source': 'claude_code_cli'
    }
    
    return True, None, token_info


def get_valid_oauth_token(provider) -> Tuple[Optional[str], Optional[str]]:
    """
    Get a valid OAuth token for the provider, refreshing if necessary.
    
    Args:
        provider: LLMProvider instance with OAuth fields
        
    Returns:
        (access_token, error_message)
    """
    from backend.database import SessionLocal
    from backend.models.llm_provider import LLMProvider
    
    if not provider.oauth_token_encrypted:
        return None, "No OAuth token configured"
    
    # Decrypt current token
    access_token = decrypt_data(provider.oauth_token_encrypted)
    
    # Check expiration
    if provider.oauth_expires_at:
        expires_at_ms = provider.oauth_expires_at.timestamp() * 1000
        if is_token_expired(expires_at_ms):
            # Need to refresh
            if not provider.oauth_refresh_token_encrypted:
                return None, "OAuth token expired and no refresh token available"
            
            refresh_token = decrypt_data(provider.oauth_refresh_token_encrypted)
            
            # Refresh the token
            new_access, new_refresh, new_expires_ms, sub_type = refresh_claude_code_token(refresh_token)
            
            if not new_access:
                return None, "Failed to refresh OAuth token"
            
            # Update database with new tokens
            db = SessionLocal()
            try:
                provider.oauth_token_encrypted = encrypt_data(new_access)
                provider.oauth_refresh_token_encrypted = encrypt_data(new_refresh)
                provider.oauth_expires_at = datetime.fromtimestamp(new_expires_ms / 1000, tz=timezone.utc)
                if sub_type:
                    provider.oauth_subscription_type = sub_type
                db.commit()
                
                access_token = new_access
            except Exception as e:
                db.rollback()
                return None, f"Failed to save refreshed token: {e}"
            finally:
                db.close()
    
    return access_token, None


def test_claude_code_connection(access_token: str) -> Tuple[bool, str]:
    """
    Test if the Claude Code token is valid by calling the profile endpoint.
    
    Returns:
        (is_valid, message)
    """
    try:
        response = requests.get(
            CLAUDE_PROFILE_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            email = data.get('email', 'unknown')
            sub_type = data.get('subscriptionType', 'unknown')
            return True, f"Connected as {email} ({sub_type})"
        elif response.status_code == 401:
            return False, "Token is invalid or expired"
        else:
            return False, f"Connection test failed: {response.status_code}"
            
    except Exception as e:
        return False, f"Connection test error: {e}"
